"""翻訳エンジン: Claude APIで日本語↔台湾華語のフランクな翻訳"""

import re
import anthropic
from app.config import Config
from app.cost_tracker import record_cost

TRANSLATE_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """あなたは翻訳機です。指示された方向にテキストを翻訳して出力するだけです。

話者情報:
- 日本語→台湾華語の場合: 送り主はRIO（男性・33歳・日本人）
- 台湾華語→日本語の場合: 送り主は友人Emily（女性・33歳・台湾人）

口調:
- 台湾華語: 「哈哈」「啦」「喔」「欸」「耶」「醬」など台湾の若者のカジュアル表現
- 日本語: 「〜だよ」「〜じゃん」「〜かな」「めっちゃ」「〜よね」など自然な口語

人称（重要）:
- 台湾華語→日本語: Emilyは女性なので一人称は「私」。「僕」「俺」は使わない
- 二人称「你」は「君」「あなた」と訳さない。省略するか名前で呼ぶ
- 家族や第三者に敬意を保つ。「そいつ」「あいつ」は使わない

絵文字: 原文の絵文字はそのまま保持。(emoji)に変換しない
文化スラング: 笑/www↔哈哈/XD、やばい↔天啊等
翻訳不要: OK/Yes/数字のみ等は「SKIP」とだけ返す

禁止:
- 翻訳結果以外の出力（感想、コメント、説明）
- 原文にない内容の追加
"""

client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)


def _is_japanese(text: str) -> bool:
    """ひらがな・カタカナが含まれていれば日本語と判定"""
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text))


async def translate(text: str) -> str | None:
    """テキストを翻訳する。翻訳不要ならNoneを返す。"""
    # コード側で言語判定し、翻訳先を明示的に指示
    if _is_japanese(text):
        instruction = f"以下の日本語を台湾華語（繁体字）に翻訳してください。日本語で出力しないでください。\n\n{text}"
    else:
        instruction = f"以下の台湾華語を日本語に翻訳してください。繁体字で出力しないでください。\n\n{text}"

    response = await client.messages.create(
        model=TRANSLATE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": instruction}],
    )

    result = response.content[0].text.strip()

    record_cost(
        model=TRANSLATE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        purpose="translate",
    )

    if result == "SKIP":
        return None

    return result
