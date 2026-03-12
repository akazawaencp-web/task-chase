"""メインアプリ: FastAPI + LINE Webhook + スケジューラー"""

import asyncio
import json
import os
import re

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from linebot.v3.webhook import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Config
from app import task_manager, line_handler, chase, x_patrol
from app.patrol_html import generate_patrol_html
from app.task_parser import parse_task_input
from app.research import research_task
from app.html_generator import generate_report_html
from app.github_pages import publish_report
from app.calendar_service import add_task_to_calendar, complete_calendar_task, reopen_calendar_task

app = FastAPI(title="Task Chase System")

# CORS設定（ダッシュボードからのAPI呼び出しを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

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
            line_handler.reply_text(event, "どれが終わった？！", quick_reply=quick_reply)
        else:
            line_handler.reply_text(event, "今タスクないよ！")
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
            line_handler.reply_text(event, "今日やるタスクないよ！")
        return

    # 手動Deep Dive リクエスト（「深掘り」「deepdive」単体の時だけ反応）
    if text.strip() in ["深掘り", "deepdive", "ディープダイブ"]:
        request_file = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "deepdive-request.json"
        request_data = {
            "requested_at": datetime.now().isoformat(),
            "status": "pending",
        }
        request_file.write_text(json.dumps(request_data, ensure_ascii=False))
        line_handler.reply_text(
            event,
            "深掘りリクエスト了解！\n数分以内にClaude Codeが動き出すよ",
        )
        return

    # あとでやる
    if text in ["あとで", "あとでやる", "明日"]:
        tasks = task_manager.get_active_tasks()
        if tasks:
            latest = tasks[-1]
            task_manager.postpone_task(latest["id"])
            line_handler.reply_text(event, f"[{latest['id']}] {latest['title']} を明日に回したよ！")
        else:
            line_handler.reply_text(event, "今タスクないよ！")
        return

    # それ以外はタスク登録として処理
    await handle_new_task(event, text)


async def handle_new_task(event: MessageEvent, text: str):
    """新しいタスクを登録→タイトル生成→reply通知（簡易調査・HTML生成は省略、deepdiveで対応）"""

    # 1. テキストからタスク情報を抽出（タイトル・ジャンル・タイプ分類）
    parsed = await parse_task_input(text)

    # 2. タスクDB登録
    task = task_manager.add_task(
        title=parsed["title"],
        description=parsed.get("description", ""),
        deadline=parsed.get("deadline", ""),
        raw_input=text,
    )
    task["task_type"] = parsed.get("task_type", "action")
    task["genre"] = parsed.get("genre", "life")
    update_fields = {
        "task_type": task["task_type"],
        "genre": task["genre"],
    }

    # 「登録だけ」が含まれていたらDeepDive対象外にする
    if "登録だけ" in text:
        update_fields["deepdive_status"] = "skipped"

    task_manager.update_task(task["id"], update_fields)

    # 3. Google Tasksに登録（タイムアウト付き）
    try:
        event_id = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: add_task_to_calendar(
                    title=task["title"],
                    deadline=task.get("deadline", ""),
                    description=task.get("description", ""),
                ),
            ),
            timeout=20,
        )
        task_manager.update_task(task["id"], {"calendar_event_id": event_id})
    except asyncio.TimeoutError:
        print(f"[Tasks] タイムアウト: {task['title']}")
    except Exception as e:
        print(f"[Tasks] 登録エラー: {e}")

    # 4. LINE返信（reply_text = プッシュメッセージ消費なし）
    deadline_str = f"\n期限: {task['deadline']}" if task.get("deadline") else ""
    skip_deepdive = "登録だけ" in text
    if skip_deepdive:
        reply_msg = f"了解、登録だけしたよ！\n\n[{task['id']}] {task['title']}{deadline_str}"
    else:
        reply_msg = f"了解、追加したよ！\n\n[{task['id']}] {task['title']}{deadline_str}\n\n深掘りしたかったら「深掘りして」って送ってね！"
    line_handler.reply_text(event, reply_msg)


async def handle_complete(event: MessageEvent, task_id: int):
    """タスク完了処理"""
    task = task_manager.get_task(task_id)
    if not task:
        line_handler.reply_text(event, f"タスク [{task_id}] 見つからないよ！")
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
        msg += f"\n\n次これどう？！\n[{next_task['id']}] {next_task['title']}"

    line_handler.reply_text(event, msg)


# === Deepdive API ===

DEEPDIVE_API_KEY = os.getenv("DEEPDIVE_API_KEY", "")


async def verify_api_key(authorization: str = Header("")):
    """Deepdive API認証"""
    if not DEEPDIVE_API_KEY or authorization != f"Bearer {DEEPDIVE_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/api/deepdive/tasks")
async def get_deepdive_tasks(_=Depends(verify_api_key)):
    """深掘り未実施のタスク一覧"""
    tasks = task_manager.get_active_tasks()
    return [t for t in tasks if t.get("deepdive_status", "") not in ("completed", "skipped")]


@app.post("/api/deepdive/upload")
async def upload_deepdive(request: Request, _=Depends(verify_api_key)):
    """深掘りHTMLをアップロード"""
    data = await request.json()
    task_id = data["task_id"]
    html_content = data["html_content"]
    filename = data.get("filename", f"rpt-dd-{os.urandom(8).hex()}.html")

    filepath = REPORTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    url = publish_report(str(filepath))

    task_manager.update_task(task_id, {
        "deepdive_status": "completed",
        "html_url": url,
    })

    return {"url": url, "filename": filename}


@app.post("/api/deepdive/skip")
async def skip_deepdive(request: Request, _=Depends(verify_api_key)):
    """タスクの深掘りをスキップ"""
    data = await request.json()
    task_manager.update_task(data["task_id"], {"deepdive_status": "skipped"})
    return {"status": "skipped"}


@app.get("/api/deepdive/check-request")
async def check_deepdive_request(_=Depends(verify_api_key)):
    """手動Deep Diveリクエストの有無を確認"""
    request_file = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "deepdive-request.json"
    if not request_file.exists():
        return {"requested": False}

    try:
        data = json.loads(request_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {"requested": False}

    if data.get("status") == "pending":
        # フラグを processing に更新（二重実行防止）
        data["status"] = "processing"
        request_file.write_text(json.dumps(data, ensure_ascii=False))
        return {"requested": True, "requested_at": data.get("requested_at", "")}

    return {"requested": False}


@app.post("/api/deepdive/clear-request")
async def clear_deepdive_request(_=Depends(verify_api_key)):
    """Deep Diveリクエストフラグをクリア"""
    request_file = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "deepdive-request.json"
    if request_file.exists():
        request_file.unlink()
    return {"status": "cleared"}


@app.post("/api/deepdive/notify")
async def notify_deepdive(request: Request, _=Depends(verify_api_key)):
    """LINE通知を送信"""
    data = await request.json()
    user_id = load_user_id()
    if not user_id:
        return {"status": "no_user_id"}
    try:
        line_handler.push_text(user_id, data["message"])
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e), "user_id_len": len(user_id)}


# === Dashboard API ===

@app.get("/api/dashboard/tasks")
async def get_dashboard_tasks(_=Depends(verify_api_key)):
    """ダッシュボード用: 全タスク一覧（完了含む）"""
    return task_manager.get_all_tasks()


@app.post("/api/dashboard/update-status")
async def update_dashboard_status(request: Request, _=Depends(verify_api_key)):
    """ダッシュボード用: タスクのステータスを更新"""
    data = await request.json()
    task_id = data["task_id"]
    new_status = data["dashboard_status"]

    valid = ("unconfirmed", "confirmed", "reinvestigate", "execute", "done")
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {valid}")

    updates = {"dashboard_status": new_status}
    if new_status == "done":
        from datetime import datetime
        updates["status"] = "completed"
        updates["completed_at"] = datetime.now().isoformat()
        updates["is_working"] = False
    else:
        updates["status"] = "active"
        updates["completed_at"] = ""

    task = task_manager.update_task(task_id, updates)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Googleカレンダー連携
    if task.get("calendar_event_id"):
        try:
            if new_status == "done":
                complete_calendar_task(task["calendar_event_id"])
            else:
                reopen_calendar_task(task["calendar_event_id"])
        except Exception:
            pass  # カレンダー連携失敗でもダッシュボード操作は成功扱い

    return task


@app.post("/api/dashboard/toggle-working")
async def toggle_working(request: Request, _=Depends(verify_api_key)):
    """ダッシュボード用: タスクの実行中フラグを切り替え"""
    data = await request.json()
    task_id = data["task_id"]
    is_working = data.get("is_working")

    current = task_manager.get_task(task_id)
    if not current:
        raise HTTPException(status_code=404, detail="Task not found")

    # 値が指定されていなければトグル
    if is_working is None:
        is_working = not current.get("is_working", False)

    task = task_manager.update_task(task_id, {"is_working": is_working})
    return task


@app.post("/api/dashboard/update-task")
async def update_dashboard_task(request: Request, _=Depends(verify_api_key)):
    """ダッシュボード用: タスクのジャンル・タイプを更新"""
    data = await request.json()
    task_id = data["task_id"]
    updates = {}
    if "genre" in data:
        updates["genre"] = data["genre"]
    if "task_type" in data:
        updates["task_type"] = data["task_type"]
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    task = task_manager.update_task(task_id, updates)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/dashboard/reclassify")
async def reclassify_all_tasks(_=Depends(verify_api_key)):
    """全タスクのジャンル・タイプを原文から再分類"""
    all_tasks = task_manager.get_all_tasks()
    updated = 0
    for t in all_tasks:
        raw = t.get("raw_input", "")
        if not raw:
            raw = t.get("title", "") + " " + t.get("description", "")
        if not raw.strip():
            continue
        try:
            parsed = await parse_task_input(raw)
            genre = parsed.get("genre", "life")
            task_type = parsed.get("task_type", "action")
            task_manager.update_task(t["id"], {"genre": genre, "task_type": task_type})
            updated += 1
        except Exception as e:
            print(f"[Reclassify] Task #{t['id']} failed: {e}")
    return {"updated": updated, "total": len(all_tasks)}


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
    scheduler.add_job(scheduled_morning_chase, "cron", hour=8, minute=0)
    scheduler.add_job(scheduled_chase, "cron", hour=12, minute=0)
    scheduler.add_job(scheduled_chase, "cron", hour=18, minute=0)
    scheduler.add_job(scheduled_monthly_report, "cron", day=1, hour=9, minute=0)
    # X自動巡回: 毎日深夜3:00に実行
    scheduler.add_job(run_x_patrol, "cron", hour=3, minute=0, id="x_patrol")
    scheduler.start()

    # 起動通知は削除（プッシュメッセージ消費を削減するため）


@app.post("/api/reports/upload")
async def upload_report_html(request: Request, _=Depends(verify_api_key)):
    """汎用HTMLアップロード（/reports/ にファイルを配置）"""
    data = await request.json()
    filename = data["filename"]
    html_content = data["html_content"]
    if "/" in filename or "\\" in filename:
        return {"error": "filename must not contain path separators"}, 400
    filepath = REPORTS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    url = f"{os.getenv('RAILWAY_PUBLIC_URL', '')}/reports/{filename}"
    return {"url": url, "filename": filename}


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nDisallow: /reports/\n"


@app.get("/")
async def root():
    return {"status": "Task Chase System is running"}


@app.get("/tasks")
async def list_tasks():
    """タスク一覧API（デバッグ用）"""
    return task_manager.get_all_tasks()


# === X自動巡回 ===

async def run_x_patrol():
    """X自動巡回を実行し、候補があればHTMLを生成してLINE通知する（cronから呼ばれる）"""
    print("[XPatrol] 巡回開始")
    user_id = load_user_id()

    candidates = await x_patrol.run_patrol(Config.XAI_API_KEY)

    if not candidates:
        print("[XPatrol] 候補なし。通知なし")
        return

    # HTMLレポートを生成
    date_str = datetime.now().strftime("%Y%m%d")
    filepath = generate_patrol_html(candidates, date_str)
    filename = Path(filepath).name

    # /reports/ 経由でアクセス可能なURLを生成
    base_url = os.getenv("RAILWAY_PUBLIC_URL", "https://web-production-5d00d.up.railway.app")
    report_url = f"{base_url}/reports/{filename}"

    print(f"[XPatrol] レポート生成: {report_url}")

    # LINE通知
    if user_id:
        msg = f"X巡回完了！{len(candidates)}件の候補があるよ\n\n{report_url}"
        try:
            line_handler.push_text(user_id, msg)
        except Exception as e:
            print(f"[XPatrol] LINE通知エラー: {e}")


@app.post("/api/patrol/submit")
async def submit_patrol_selections(request: Request):
    """巡回HTMLからチェックされた候補を受け取り、タスク登録する"""
    data = await request.json()
    pin = data.get("pin", "")
    selected = data.get("selected", [])  # {url, text, title} のリスト

    # PIN検証（環境変数 PATROL_PIN と照合）
    if pin != Config.PATROL_PIN:
        return {"error": "PINが正しくありません"}

    if not selected:
        return {"error": "候補が選択されていません"}

    # 各候補をタスク登録
    registered = []
    for item in selected:
        task = task_manager.add_task(
            title=item.get("title", "X投稿深掘り"),
            description=item.get("text", "")[:200],
            raw_input=item.get("url", ""),
        )
        registered.append(task["id"])

    # 既読リストに追加（次回巡回で除外）
    x_patrol.add_to_checked(item["url"] for item in selected)

    print(f"[XPatrol] {len(registered)}件のタスクを登録: {registered}")
    return {"message": f"{len(registered)}件のタスクを登録しました", "task_ids": registered}


@app.post("/api/patrol/run")
async def manual_patrol_run():
    """X巡回を手動で即時実行（バックグラウンド）"""
    import asyncio
    print("[XPatrol] 手動実行リクエスト受信")
    has_key = bool(Config.XAI_API_KEY)
    if not has_key:
        return {"status": "error", "message": "XAI_API_KEY未設定"}
    asyncio.create_task(run_x_patrol())
    return {"status": "patrol started in background", "has_api_key": has_key}


@app.get("/api/patrol/status")
async def patrol_status():
    """最新の巡回レポートの状態を確認"""
    reports_dir = REPORTS_DIR
    if not reports_dir.exists():
        return {"status": "no reports yet"}
    patrol_files = sorted(reports_dir.glob("patrol-*.html"), reverse=True)
    if not patrol_files:
        return {"status": "no patrol reports found"}
    latest = patrol_files[0]
    return {
        "status": "ok",
        "latest_report": latest.name,
        "url": f"{os.getenv('RAILWAY_PUBLIC_URL', '')}/reports/{latest.name}",
    }
