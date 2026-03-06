"""設定管理: 環境変数から各種APIキーを読み込む"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # LINE
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

    # Claude API
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Google Calendar
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")

    # GitHub Pages
    GITHUB_REPO = os.getenv("GITHUB_REPO", "akazawaencp-web/task-chase")
    GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "https://akazawaencp-web.github.io/task-chase")

    # Server
    PORT = int(os.getenv("PORT", "8000"))
