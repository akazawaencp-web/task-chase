#!/bin/bash
# ============================================================
# DeepDive Watcher - 手動Deep Diveリクエスト監視スクリプト
#
# Macのタイマー(launchd)から5分ごとに呼ばれる。
# RailwayにDeep Diveリクエストがあれば auto-deepdive.sh を実行。
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/auto-deepdive.log"

# --- ログ関数 ---
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [watcher] $1" >> "$LOG_FILE"
}

# --- リクエスト確認 ---
RESULT=$(python3 "$SCRIPT_DIR/deepdive_client.py" check-request 2>&1)

if [ $? -ne 0 ]; then
    log "ERROR: リクエスト確認失敗: $RESULT"
    exit 1
fi

# JSON から requested フィールドを取得
REQUESTED=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print('true' if data.get('requested') else 'false')
except:
    print('false')
" 2>/dev/null)

if [ "$REQUESTED" = "true" ]; then
    log "手動Deep Diveリクエスト検出 → auto-deepdive.sh を起動"
    bash "$SCRIPT_DIR/auto-deepdive.sh"
    EXIT_CODE=$?

    # リクエストフラグをクリア
    python3 "$SCRIPT_DIR/deepdive_client.py" clear-request >> "$LOG_FILE" 2>&1

    if [ $EXIT_CODE -eq 0 ]; then
        log "手動Deep Dive 正常完了"
    else
        log "手動Deep Dive 異常終了 (exit code: $EXIT_CODE)"
    fi
fi
