"""タスク解析: 音声入力のテキストからタイトル・説明・期限を自動抽出"""

import anthropic
from app.config import Config
from app.cost_tracker import record_cost


async def parse_task_input(user_text: str) -> dict:
    """ユーザーの自然言語入力をタスク情報に分解する"""

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""以下のテキストからタスク情報を抽出してJSON形式で返してください。

テキスト: 「{user_text}」

以下のJSON形式で返してください（他の文章は不要、JSONのみ）:
{{
  "title": "タスクのタイトル（一言に要約）",
  "description": "補足説明（あれば。なければ空文字）",
  "deadline": "期限（YYYY-MM-DD形式。なければ空文字）",
  "task_type": "action または research"
}}

ルール:
- titleは短く一言にまとめる（10文字以内が理想）
- 長文の場合、要点をtitleに、詳細をdescriptionに分ける
- 期限は「来週まで」「4月22日まで」等の自然言語から計算する
- 今日の日付を基準にする
- 期限がない場合はdeadlineを空文字にする
- 行動が必要なタスクはaction、調べもの・考え事はresearch"""
            }
        ],
    )

    record_cost("claude-sonnet-4-20250514", message.usage.input_tokens, message.usage.output_tokens, "タスク解析")

    response_text = message.content[0].text.strip()

    # JSON部分を抽出
    if "```" in response_text:
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()

    import json
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "title": user_text[:20],
            "description": user_text,
            "deadline": "",
            "task_type": "action",
        }
