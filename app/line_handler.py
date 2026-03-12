"""LINE連携: メッセージの受信と送信"""

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from app.config import Config

configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)


def reply_text(event: MessageEvent, text: str, quick_reply=None):
    """LINEにテキストメッセージを返信"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        msg = TextMessage(text=text)
        if quick_reply:
            msg.quick_reply = quick_reply
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[msg],
            )
        )


def push_text(user_id: str, text: str):
    """LINEにプッシュメッセージを送信"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)],
            )
        )


def format_task_registered(task: dict) -> str:
    """タスク登録完了メッセージ"""
    deadline_str = f"\n期限: {task['deadline']}" if task.get("deadline") else ""
    return f"""了解、追加したよ

[{task['id']}] {task['title']}{deadline_str}

深掘りしたかったら「深掘りして」って送ってね"""


def format_task_researched(task: dict, html_url: str) -> str:
    """調査完了メッセージ"""
    return f"""[{task['id']}] {task['title']} の調査終わったよ

詳しくはこっち見てね
{html_url}

終わったら「{task['id']}完了」って送ってね"""


def format_task_completed(task: dict) -> str:
    """タスク完了メッセージ"""
    return f"""[{task['id']}] {task['title']} 完了にしたよ

おつかれ!"""


def format_task_list(tasks: list[dict]) -> str:
    """タスク一覧メッセージ"""
    if not tasks:
        return "今タスクないよ"

    lines = ["-- 未完了タスク --\n"]
    for t in tasks:
        deadline_str = f" (期限: {t['deadline']})" if t.get("deadline") else ""
        lines.append(f"[{t['id']}] {t['title']}{deadline_str}")

    lines.append(f"\n全{len(tasks)}件")
    return "\n".join(lines)
