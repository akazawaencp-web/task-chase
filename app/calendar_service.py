"""Google Tasks連携: タスクの登録・完了"""

import json
import os
from datetime import datetime
from pathlib import Path

import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]
TOKEN_PATH = Path(__file__).parent.parent / "token.json"


def _get_tasks_service():
    """認証済みのTasks APIサービスを返す"""
    creds = None

    token_b64 = os.getenv("GOOGLE_TOKEN_JSON", "")

    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode("utf-8")
            token_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"[Tasks] トークン解析エラー: {e}")
    elif TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("Google Tasksの認証トークンがありません。ローカルでauth_google.pyを実行してください。")

    return build("tasks", "v1", credentials=creds)


def add_task_to_calendar(title: str, deadline: str = "", description: str = "") -> str:
    """Google Tasksにタスクを登録し、タスクIDを返す"""
    service = _get_tasks_service()

    task_body = {
        "title": title,
        "notes": description,
    }

    if deadline:
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
