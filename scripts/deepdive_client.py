#!/usr/bin/env python3
"""Deepdive API Client - Claude Code から Railway API にアクセスするためのスクリプト"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# .env から環境変数を読み込む（python-dotenv不要）
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

API_URL = os.getenv("RAILWAY_API_URL", "https://web-production-5d00d.up.railway.app")
API_KEY = os.getenv("DEEPDIVE_API_KEY", "")


def _request(method, path, data=None):
    """APIリクエストを送信"""
    url = f"{API_URL}{path}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def fetch():
    """深掘り対象のタスク一覧を取得"""
    result = _request("GET", "/api/deepdive/tasks")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def upload(task_id, html_path, filename):
    """深掘りHTMLをアップロード"""
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    result = _request("POST", "/api/deepdive/upload", {
        "task_id": int(task_id),
        "html_content": html_content,
        "filename": filename,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def skip(task_id):
    """タスクの深掘りをスキップ"""
    result = _request("POST", "/api/deepdive/skip", {"task_id": int(task_id)})
    print(json.dumps(result, ensure_ascii=False, indent=2))


def notify(message):
    """LINE通知を送信"""
    result = _request("POST", "/api/deepdive/notify", {"message": message})
    print(json.dumps(result, ensure_ascii=False, indent=2))


def update_status(task_id, dashboard_status):
    """タスクのダッシュボードステータスを更新"""
    result = _request("POST", "/api/dashboard/update-status", {
        "task_id": int(task_id),
        "dashboard_status": dashboard_status,
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


def reclassify():
    """全タスクのジャンル・タイプを再分類"""
    url = f"{API_URL}/api/dashboard/reclassify"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def toggle_working(task_id, is_working=None):
    """タスクの実行中フラグを切り替え"""
    payload = {"task_id": int(task_id)}
    if is_working is not None:
        payload["is_working"] = is_working
    result = _request("POST", "/api/dashboard/toggle-working", payload)
    status = "実行中" if result.get("is_working") else "停止"
    print(f"Task #{task_id}: {status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: deepdive_client.py <fetch|upload|skip|notify|update-status|working|reclassify> [args...]")
        print()
        print("Commands:")
        print("  fetch                              - 深掘り対象タスク一覧")
        print("  upload <task_id> <html> <name>      - HTMLアップロード")
        print("  skip <task_id>                      - タスクスキップ")
        print("  notify <message>                    - LINE通知送信")
        print("  update-status <task_id> <status>    - ダッシュボードステータス更新")
        print("    status: unconfirmed/confirmed/reinvestigate/execute/done")
        print("  working <task_id> [on|off]          - 実行中マーク切り替え")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "fetch":
        fetch()
    elif cmd == "upload":
        if len(sys.argv) < 5:
            print("Usage: deepdive_client.py upload <task_id> <html_path> <filename>", file=sys.stderr)
            sys.exit(1)
        upload(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "skip":
        if len(sys.argv) < 3:
            print("Usage: deepdive_client.py skip <task_id>", file=sys.stderr)
            sys.exit(1)
        skip(sys.argv[2])
    elif cmd == "notify":
        if len(sys.argv) < 3:
            print("Usage: deepdive_client.py notify <message>", file=sys.stderr)
            sys.exit(1)
        notify(" ".join(sys.argv[2:]))
    elif cmd == "update-status":
        if len(sys.argv) < 4:
            print("Usage: deepdive_client.py update-status <task_id> <status>", file=sys.stderr)
            sys.exit(1)
        update_status(sys.argv[2], sys.argv[3])
    elif cmd == "working":
        if len(sys.argv) < 3:
            print("Usage: deepdive_client.py working <task_id> [on|off]", file=sys.stderr)
            sys.exit(1)
        w = None
        if len(sys.argv) >= 4:
            w = sys.argv[3].lower() == "on"
        toggle_working(sys.argv[2], w)
    elif cmd == "reclassify":
        reclassify()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
