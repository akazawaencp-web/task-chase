"""Google Tasks連携: タスクの登録・完了"""

import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]
TOKEN_PATH = Path(__file__).parent.parent / "token.json"
VOLUME_TOKEN_PATH = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "google_token.json"


def _refresh_with_timeout(creds, timeout=10):
    """タイムアウト付きでトークンをリフレッシュ"""
    error = [None]

    def do_refresh():
        try:
            creds.refresh(Request())
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=do_refresh)
    t.start()
    t.join(timeout)

    if t.is_alive():
        raise TimeoutError(f"トークンリフレッシュが{timeout}秒でタイムアウト")
    if error[0]:
        raise error[0]


def _get_tasks_service():
    """認証済みのTasks APIサービスを返す"""
    creds = None

    # 1. まずVolumeに保存されたトークンを試す（リフレッシュ済みの新しいトークン）
    if VOLUME_TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(VOLUME_TOKEN_PATH), SCOPES)
        except Exception:
            pass

    # 2. なければ環境変数から読む
    if not creds:
        token_b64 = os.getenv("GOOGLE_TOKEN_JSON", "")
        if token_b64:
            try:
                token_json = base64.b64decode(token_b64).decode("utf-8")
                token_data = json.loads(token_json)
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            except Exception as e:
                print(f"[Tasks] トークン解析エラー: {e}")

    # 3. ローカルのtoken.json（開発用）
    if not creds and TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds:
        raise RuntimeError("Google Tasksの認証トークンがありません。")

    # 4. 期限切れならリフレッシュ（タイムアウト付き）
    if not creds.valid and creds.expired and creds.refresh_token:
        _refresh_with_timeout(creds, timeout=10)
        # リフレッシュ後のトークンをVolumeに保存（次回はリフレッシュ不要）
        try:
            VOLUME_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(VOLUME_TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception:
            pass

    return build("tasks", "v1", credentials=creds)


def add_task_to_calendar(title: str, deadline: str = "", description: str = "") -> str:
    """Google Tasksにタスクを登録し、タスクIDを返す"""
    service = _get_tasks_service()

    task_body = {
        "title": title,
        "notes": description,
    }

    if not deadline:
        deadline = datetime.now(JST).strftime("%Y-%m-%d")
    task_body["due"] = f"{deadline}T00:00:00.000Z"

    result = service.tasks().insert(tasklist="@default", body=task_body).execute()

    return result.get("id", "")


def complete_calendar_task(task_id: str):
    """Google Tasksのタスクを完了にする"""
    if not task_id:
        return

    service = _get_tasks_service()

    service.tasks().patch(
        tasklist="@default",
        task=task_id,
        body={"status": "completed"},
    ).execute()
