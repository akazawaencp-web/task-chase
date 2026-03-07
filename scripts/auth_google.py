"""Googleカレンダー認証スクリプト（ローカルで1回だけ実行）

ブラウザが開くのでGoogleアカウントでログインすると、
token.jsonが生成される。
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "token.json")


def main():
    print("Googleカレンダーの認証を開始します...")
    print("ブラウザが開くので、Googleアカウントでログインしてください。")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print()
    print("認証完了! token.json が生成されました。")
    print()
    print("次のステップ: token.jsonの中身をRailwayの環境変数に設定します。")
    print("以下の内容をコピーしてください:")
    print()

    with open(TOKEN_PATH, "r") as f:
        token_data = f.read()

    print("--- ここから ---")
    print(token_data)
    print("--- ここまで ---")


if __name__ == "__main__":
    main()
