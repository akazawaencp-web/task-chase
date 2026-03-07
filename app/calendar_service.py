"""Googleカレンダー連携: タスクの登録・完了・予定の参照"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import Config

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = Path(__file__).parent.parent / "token.json"


def _get_service():
    """認証済みのCalendar APIサービスを返す"""
    creds = None

    # 環境変数からトークンを読む（Railway用）
    token_json = os.getenv("GOOGLE_TOKEN_JSON", "")
    print(f"[Calendar] GOOGLE_TOKEN_JSON exists: {bool(token_json)}, length: {len(token_json)}")

    if token_json:
        try:
            token_data = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print(f"[Calendar] creds loaded, valid: {creds.valid}, expired: {creds.expired}")
        except Exception as e:
            print(f"[Calendar] トークン解析エラー: {e}")
    elif TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Calendar] トークンをリフレッシュ中...")
            creds.refresh(Request())
            print("[Calendar] リフレッシュ成功")
        else:
            raise RuntimeError("Googleカレンダーの認証トークンがありません。ローカルでauth_google.pyを実行してください。")

    return build("calendar", "v3", credentials=creds)


def add_task_to_calendar(title: str, deadline: str = "", description: str = "") -> str:
    """Googleカレンダーにタスク（終日イベント）を登録し、イベントIDを返す"""
    service = _get_service()

    if deadline:
        start_date = deadline
    else:
        start_date = datetime.now().strftime("%Y-%m-%d")

    event = {
        "summary": f"[タスク] {title}",
        "description": description,
        "start": {"date": start_date},
        "end": {"date": start_date},
        "colorId": "4",  # コーラルっぽい色
    }

    result = service.events().insert(
        calendarId=Config.GOOGLE_CALENDAR_ID, body=event
    ).execute()

    return result.get("id", "")


def complete_calendar_task(event_id: str):
    """カレンダーのタスクを完了にする（タイトルに完了マークを追加）"""
    if not event_id:
        return

    service = _get_service()

    event = service.events().get(
        calendarId=Config.GOOGLE_CALENDAR_ID, eventId=event_id
    ).execute()

    event["summary"] = event["summary"].replace("[タスク]", "[完了]")
    event["colorId"] = "10"  # 緑

    service.events().update(
        calendarId=Config.GOOGLE_CALENDAR_ID, eventId=event_id, body=event
    ).execute()


def get_upcoming_events(days: int = 7) -> list[dict]:
    """今後N日間の予定を取得"""
    service = _get_service()

    now = datetime.utcnow().isoformat() + "Z"
    end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

    result = service.events().list(
        calendarId=Config.GOOGLE_CALENDAR_ID,
        timeMin=now,
        timeMax=end,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return result.get("items", [])
