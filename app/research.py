"""調査エンジン: タスクの詳細調査をClaude Sonnetで実行"""

import anthropic
from app.config import Config
from app.cost_tracker import record_cost


async def research_task(title: str, description: str = "", task_type: str = "action") -> dict:
    """タスクを詳細調査して構造化データを返す"""

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    if task_type == "research":
        prompt = _build_research_prompt(title, description)
    else:
        prompt = _build_action_prompt(title, description)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    record_cost("claude-sonnet-4-20250514", message.usage.input_tokens, message.usage.output_tokens, "タスク調査")

    response_text = message.content[0].text.strip()

    # JSON抽出
    if "```" in response_text:
        parts = response_text.split("```")
        for part in parts[1:]:
            if part.startswith("json"):
                part = part[4:]
            part = part.strip()
            try:
                import json
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    # JSONが取れなかった場合のフォールバック
    return {
        "next_action": "調査結果を確認してください",
        "checklist": [{"item": title, "done": False, "depends_on": ""}],
        "time_estimate": "不明",
        "cost_estimate": "不明",
        "risk": "調査結果が正しく取得できませんでした",
        "hassle_points": [],
        "details": response_text,
        "evidence": [],
        "schedule_suggestion": "",
    }


def _build_action_prompt(title: str, description: str) -> str:
    desc_part = f"\n補足: {description}" if description else ""
    return f"""以下のタスクについて詳細に調査してください。

タスク: {title}{desc_part}

以下のJSON形式で返してください（他の文章は不要、JSONのみ）:
{{
  "next_action": "最初にやるべき具体的な一歩（大きく表示される）",
  "checklist": [
    {{"item": "やること1", "done": false, "depends_on": ""}},
    {{"item": "やること2（やること1の後）", "done": false, "depends_on": "やること1"}},
    {{"item": "やること3", "done": false, "depends_on": ""}}
  ],
  "time_estimate": "全体の所要時間（例: 約2時間）",
  "cost_estimate": "かかる費用（例: 3,850円）",
  "risk": "やらなかった場合のリスク（具体的に）",
  "hassle_points": [
    {{"point": "面倒ポイント1", "solution": "解消策1"}},
    {{"point": "面倒ポイント2", "solution": "解消策2"}}
  ],
  "details": "詳細情報（折りたたみ表示用、200文字程度）",
  "evidence": ["参考情報1", "参考情報2"],
  "schedule_suggestion": "おすすめの実施タイミング（例: 平日午前中がおすすめ）"
}}

調査のルール:
- 5W1Hで要素分解する
- 依存関係を2段階以上チェック（例: 免許更新→写真が必要→証明写真を撮る）
- 所要時間と費用を具体的に見積もる
- やらなかった場合のリスクを明示する
- 面倒ポイントを予測して解消策を先回り提示する
- 着手ハードルを下げる分解にする
- 日本の情報・日本語で回答する"""


def _build_research_prompt(title: str, description: str) -> str:
    desc_part = f"\n補足: {description}" if description else ""
    return f"""以下のテーマについて調査・整理してください。

テーマ: {title}{desc_part}

以下のJSON形式で返してください（他の文章は不要、JSONのみ）:
{{
  "next_action": "このテーマについて最初に考えるべきポイント",
  "checklist": [
    {{"item": "調査・検討項目1", "done": false, "depends_on": ""}},
    {{"item": "調査・検討項目2", "done": false, "depends_on": ""}},
    {{"item": "調査・検討項目3", "done": false, "depends_on": ""}}
  ],
  "time_estimate": "検討に必要な目安時間",
  "cost_estimate": "関連費用（あれば）",
  "risk": "検討しないまま放置した場合のリスク",
  "hassle_points": [
    {{"point": "つまずきやすいポイント", "solution": "考え方のヒント"}}
  ],
  "details": "調査結果の要約（300文字程度、要点を整理）",
  "evidence": ["参考になる情報源1", "参考になる情報源2"],
  "schedule_suggestion": "いつまでに結論を出すのがおすすめか"
}}

調査のルール:
- 複数の観点から整理する
- 具体的な選択肢やフレームワークを提示する
- 抽象的にならず、実用的な内容にする
- 日本の情報・日本語で回答する"""
