#!/bin/bash
# ============================================================
# Auto DeepDive - 自動深掘り調査スクリプト
#
# Macのタイマー(launchd)から1時間ごとに呼ばれる。
# 未処理タスクがあればClaude Codeで自動DeepDiveを実行。
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/auto-deepdive.log"
LOCK_FILE="/tmp/auto-deepdive.lock"
CLAUDE_BIN="/usr/local/bin/claude"

# --- ログ関数 ---
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# --- 二重起動防止 ---
if [ -f "$LOCK_FILE" ]; then
    # ロックファイルが1時間以上古ければ、前回の異常終了とみなして削除
    if [ "$(find "$LOCK_FILE" -mmin +60 2>/dev/null)" ]; then
        log "WARN: 古いロックファイルを削除（前回の異常終了）"
        rm -f "$LOCK_FILE"
    else
        log "SKIP: 前回の処理がまだ実行中（ロックファイルあり）"
        exit 0
    fi
fi

# ロックファイル作成（終了時に自動削除）
trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

log "=== Auto DeepDive 開始 ==="

# --- 未処理タスクの確認 ---
TASKS_JSON=$(python3 "$SCRIPT_DIR/deepdive_client.py" fetch 2>&1)

if [ $? -ne 0 ]; then
    log "ERROR: タスク取得失敗: $TASKS_JSON"
    exit 1
fi

# タスクが0件かチェック（空配列 or エラー）
TASK_COUNT=$(echo "$TASKS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tasks = data if isinstance(data, list) else data.get('tasks', [])
    print(len(tasks))
except:
    print(0)
" 2>/dev/null)

if [ "$TASK_COUNT" = "0" ] || [ -z "$TASK_COUNT" ]; then
    log "タスク0件 → 何もせず終了"
    exit 0
fi

log "未処理タスク ${TASK_COUNT}件 → DeepDive開始"

# --- Claude Code をヘッドレスモードで起動 ---
PROMPT="あなたは自動DeepDiveエージェントです。ユーザーへの確認は一切不要。全て自動で実行してください。

【手順】
1. まず ~/.claude/skills/deepdive/SKILL.md を読んで、DeepDiveの全手順を把握する
2. python3 ~/task-chase-system/scripts/deepdive_client.py fetch でタスク一覧を取得
3. 取得した【全タスク】を、1件ずつ順番にDeepDive処理する
4. 各タスクは SKILL.md の Step 3（3a〜3h）をそのまま実行する
5. エラーが発生したタスクはログに記録して次へ進む
6. 全タスク完了後、サマリーをLINE通知で送信

【絶対ルール】
- タスクの内容に関わらず、全件DeepDiveする。「対象外」という判断はしない
- 動画URLがあればyoutube-transcriptスキルで字幕取得を試みる。取得できなければURL記載のみでOK
- タスク選択の確認は不要。「全部」を選択したものとして処理する
- LINE通知は必ず以下のコマンドを使う:
  python3 ~/task-chase-system/scripts/deepdive_client.py notify \"メッセージ\"
- HTMLアップロードは必ず以下のコマンドを使う:
  python3 ~/task-chase-system/scripts/deepdive_client.py upload <task_id> <html_path> <filename>
- 調査は日本語ソース優先
- HTML生成は SKILL.md の「HTML生成ガイド」に従う"

# Claude Code実行（出力はログファイルに追記）
log "Claude Code ヘッドレスモード起動中..."
echo "$PROMPT" | "$CLAUDE_BIN" -p \
    --dangerously-skip-permissions \
    --model sonnet \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Agent,Skill" \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "=== Auto DeepDive 正常完了 ==="
else
    log "=== Auto DeepDive 異常終了 (exit code: $EXIT_CODE) ==="
fi

exit $EXIT_CODE
