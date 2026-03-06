"""LINEリッチメニュー作成スクリプト（ローカルで1回実行）"""

import json
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# リッチメニュー定義（6ボタン: 2行3列）
RICH_MENU = {
    "size": {"width": 2500, "height": 1686},
    "selected": True,
    "name": "タスクチェイスメニュー",
    "chatBarText": "メニュー",
    "areas": [
        {
            "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
            "action": {"type": "message", "text": "タスク追加"},
        },
        {
            "bounds": {"x": 833, "y": 0, "width": 834, "height": 843},
            "action": {"type": "message", "text": "今日のタスク"},
        },
        {
            "bounds": {"x": 1667, "y": 0, "width": 833, "height": 843},
            "action": {"type": "message", "text": "完了報告"},
        },
        {
            "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
            "action": {"type": "message", "text": "今週のまとめ"},
        },
        {
            "bounds": {"x": 833, "y": 843, "width": 834, "height": 843},
            "action": {"type": "message", "text": "あとでやる"},
        },
        {
            "bounds": {"x": 1667, "y": 843, "width": 833, "height": 843},
            "action": {"type": "message", "text": "タスク一覧"},
        },
    ],
}


def create_rich_menu():
    # 1. リッチメニュー作成
    resp = httpx.post(
        "https://api.line.me/v2/bot/richmenu",
        headers=HEADERS,
        json=RICH_MENU,
    )
    resp.raise_for_status()
    rich_menu_id = resp.json()["richMenuId"]
    print(f"リッチメニュー作成完了: {rich_menu_id}")

    # 2. メニュー画像をアップロード
    image_path = os.path.join(os.path.dirname(__file__), "rich_menu_image.png")
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            resp = httpx.post(
                f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Content-Type": "image/png",
                },
                content=f.read(),
            )
            resp.raise_for_status()
            print("画像アップロード完了")
    else:
        print(f"画像ファイルが見つかりません: {image_path}")
        print("画像なしで続行します（後から設定可能）")

    # 3. デフォルトリッチメニューに設定
    resp = httpx.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
        headers=HEADERS,
    )
    resp.raise_for_status()
    print("デフォルトメニューに設定完了")

    return rich_menu_id


if __name__ == "__main__":
    create_rich_menu()
