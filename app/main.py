"""メインアプリ: FastAPI + LINE Webhook + スケジューラー"""

import asyncio
import os
import re

from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Config
from app import task_manager, line_handler, chase
from app.task_parser import parse_task_input
from app.research import research_task
from app.html_generator import generate_report_html
from app.github_pages import publish_report
from app.calendar_service import add_task_to_calendar, complete_calendar_task

app = FastAPI(title="Task Chase System")

# HTML配信用: /reports/ でHTMLファイルにアクセス可能にする
REPORTS_DIR = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data") + "/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")
parser = WebhookParser(Config.LINE_CHANNEL_SECRET)

# ユーザーIDを保存（シングルユーザー前提）
USER_ID_FILE = os.path.join(os.getenv("DATA_DIR", "/tmp/task-chase-data"), "user_id.txt")


def save_user_id(user_id: str):
    with open(USER_ID_FILE, "w") as f:
        f.write(user_id)


def load_user_id() -> str:
    try:
        with open(USER_ID_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


@app.post("/webhook")
async def webhook(request: Request):
    """LINE Webhookエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            user_id = event.source.user_id
            save_user_id(user_id)
            await handle_message(event, event.message.text)

    return {"status": "ok"}


async def handle_message(event: MessageEvent, text: str):
    """メッセージの内容に応じて処理を振り分ける"""
    text = text.strip()

    # 完了報告: 「1完了」「完了1」等
    match = re.match(r"(\d+)\s*完了|完了\s*(\d+)", text)
    if match:
        task_id = int(match.group(1) or match.group(2))
        await handle_complete(event, task_id)
        return

    # 費用レポート
    if text in ["費用", "コスト", "API費用"]:
        from app.cost_tracker import format_monthly_report
        line_handler.reply_text(event, format_monthly_report())
        return

    # 完了報告（リッチメニューから）
    if text == "完了報告":
        tasks = task_manager.get_active_tasks()
        if tasks:
            from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
            items = []
            for t in tasks[:13]:  # クイックリプライは最大13個
                items.append(
                    QuickReplyItem(
                        action=MessageAction(
                            label=f"{t['title'][:12]}",
                            text=f"{t['id']}完了",
                        )
                    )
                )
            quick_reply = QuickReply(items=items)
            line_handler.reply_text(event, "完了したタスクをタップしてね!", quick_reply=quick_reply)
        else:
            line_handler.reply_text(event, "未完了のタスクはありません。")
        return

    # 今週のまとめ
    if text in ["今週", "今週のまとめ"]:
        tasks = task_manager.get_active_tasks()
        completed = [t for t in task_manager._load_tasks() if t["status"] == "completed"]
        msg = f"-- 今週のまとめ --\n\n未完了: {len(tasks)}件\n完了済み: {len(completed)}件"
        if tasks:
            msg += "\n\n-- 未完了タスク --"
            for t in tasks:
                deadline_str = f"（期限: {t['deadline']}）" if t.get("deadline") else ""
                msg += f"\n[{t['id']}] {t['title']}{deadline_str}"
        line_handler.reply_text(event, msg)
        return

    # タスク一覧
    if text in ["一覧", "タスク一覧", "リスト"]:
        tasks = task_manager.get_active_tasks()
        line_handler.reply_text(event, line_handler.format_task_list(tasks))
        return

    # 今日のタスク
    if text in ["今日", "今日のタスク"]:
        tasks = task_manager.get_today_tasks()
        if tasks:
            # まず一覧を表示
            lines = [f"-- 今日のタスク（{len(tasks)}件）--\n"]
            for t in tasks:
                deadline_str = f"（期限: {t['deadline']}）" if t.get("deadline") else ""
                lines.append(f"[{t['id']}] {t['title']}{deadline_str}")
            task_list = "\n".join(lines)

            # AIのチェイスメッセージを生成
            chase_msg = await chase.generate_morning_chase()

            line_handler.reply_text(event, f"{task_list}\n\n{chase_msg}")
        else:
            line_handler.reply_text(event, "今日やるタスクはありません。")
        return

    # あとでやる
    if text in ["あとで", "あとでやる", "明日"]:
        tasks = task_manager.get_active_tasks()
        if tasks:
            latest = tasks[-1]
            task_manager.postpone_task(latest["id"])
            line_handler.reply_text(event, f"[{latest['id']}] {latest['title']} を明日に回しました。")
        else:
            line_handler.reply_text(event, "未完了のタスクはありません。")
        return

    # それ以外はタスク登録として処理
    await handle_new_task(event, text)


async def handle_new_task(event: MessageEvent, text: str):
    """新しいタスクを登録→調査→HTML生成→LINE通知"""

    # 1. 登録中メッセージ
    line_handler.reply_text(event, "タスクを登録中...")

    # 2. テキストからタスク情報を抽出
    parsed = await parse_task_input(text)

    # 3. タスクDB登録
    task = task_manager.add_task(
        title=parsed["title"],
        description=parsed.get("description", ""),
        deadline=parsed.get("deadline", ""),
        raw_input=text,
    )
    task["task_type"] = parsed.get("task_type", "action")

    # 4. Googleカレンダーに登録
    try:
        event_id = add_task_to_calendar(
            title=task["title"],
            deadline=task.get("deadline", ""),
            description=task.get("description", ""),
        )
        task_manager.update_task(task["id"], {"calendar_event_id": event_id})
        print(f"[Calendar] 登録成功: {task['title']}")
    except Exception as e:
        print(f"[Calendar] 登録失敗: {e}")  # エラーをログに出す

    # 5. 詳細調査（原文も渡してクオリティを保つ）
    research_result = await research_task(
        title=task["title"],
        description=task.get("description", ""),
        task_type=task.get("task_type", "action"),
        raw_input=text,
    )

    # 6. HTML生成（原文も渡して深掘りプロンプトを生成）
    html_path = generate_report_html(task, research_result, raw_input=text)

    # 7. GitHub Pagesにデプロイ
    html_url = publish_report(html_path)

    if html_url:
        task_manager.update_task(task["id"], {"html_url": html_url})

    # 8. LINE通知（プッシュメッセージ）
    user_id = event.source.user_id
    if html_url:
        line_handler.push_text(
            user_id,
            line_handler.format_task_researched(task, html_url),
        )
    else:
        line_handler.push_text(
            user_id,
            f"[{task['id']}] {task['title']} を登録しました。\n\n調査結果の公開に失敗しました。再度試してください。",
        )


async def handle_complete(event: MessageEvent, task_id: int):
    """タスク完了処理"""
    task = task_manager.get_task(task_id)
    if not task:
        line_handler.reply_text(event, f"タスク [{task_id}] が見つかりません。")
        return

    # タスクDB完了
    task_manager.complete_task(task_id)

    # カレンダー完了
    if task.get("calendar_event_id"):
        try:
            complete_calendar_task(task["calendar_event_id"])
        except Exception:
            pass

    # 完了通知 + 次のタスク提案
    msg = line_handler.format_task_completed(task)

    # 次のタスク提案
    remaining = task_manager.get_active_tasks()
    if remaining:
        next_task = remaining[0]
        msg += f"\n\n次はこれどうですか?\n[{next_task['id']}] {next_task['title']}"

    line_handler.reply_text(event, msg)


# === スケジューラー ===

scheduler = AsyncIOScheduler()


async def scheduled_morning_chase():
    """朝のチェイス（毎日8:00）"""
    user_id = load_user_id()
    if not user_id:
        return

    msg = await chase.generate_morning_chase()
    line_handler.push_text(user_id, msg)


async def scheduled_chase():
    """定期チェイス（毎日12:00, 18:00）"""
    user_id = load_user_id()
    if not user_id:
        return

    tasks = chase.get_tasks_needing_chase()
    for task in tasks[:3]:  # 最大3件
        msg = await chase.generate_chase_for_task(task)
        line_handler.push_text(user_id, msg)
        task_manager.record_chase(task["id"])


async def scheduled_monthly_report():
    """月次レポート（毎月1日 9:00）"""
    user_id = load_user_id()
    if not user_id:
        return

    from app.cost_tracker import format_monthly_report
    line_handler.push_text(user_id, format_monthly_report())


@app.on_event("startup")
async def startup():
    """アプリ起動時にスケジューラーを開始"""
    # デバッグ: 環境変数の確認
    import os
    env_names = [k for k in os.environ.keys() if k.startswith("GOOGLE") or k.startswith("LINE") or k.startswith("ANTHROPIC")]
    print(f"[Debug] 関連する環境変数: {env_names}")
    token_val = os.getenv("GOOGLE_TOKEN_JSON", "")
    print(f"[Debug] GOOGLE_TOKEN_JSON length at startup: {len(token_val)}")
    data_dir = os.getenv("DATA_DIR", "/tmp/task-chase-data")
    print(f"[Debug] DATA_DIR env: {os.getenv('DATA_DIR', 'NOT SET')}")
    print(f"[Debug] DATA_DIR resolved: {data_dir}")
    print(f"[Debug] /data exists: {os.path.exists('/data')}")
    print(f"[Debug] /data contents: {os.listdir('/data') if os.path.exists('/data') else 'N/A'}")
    scheduler.add_job(scheduled_morning_chase, "cron", hour=8, minute=0)
    scheduler.add_job(scheduled_chase, "cron", hour=12, minute=0)
    scheduler.add_job(scheduled_chase, "cron", hour=18, minute=0)
    scheduler.add_job(scheduled_monthly_report, "cron", day=1, hour=9, minute=0)
    scheduler.start()


@app.get("/")
async def root():
    return {"status": "Task Chase System is running"}


@app.get("/tasks")
async def list_tasks():
    """タスク一覧API（デバッグ用）"""
    return task_manager.get_active_tasks()
