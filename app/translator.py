"""翻訳エンジン: Claude APIで日本語↔台湾華語のフランクな翻訳"""

import anthropic
from app.config import Config
from app.cost_tracker import record_cost

TRANSLATE_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """あなたは日本語と台湾華語（繁体字中国語）の間でリアルタイム翻訳する通訳です。
33歳の仲の良い友達同士のLINEトークを翻訳しています。

## 翻訳ルール
- 日本語 → 台湾華語（繁体字）に翻訳
- 台湾華語/中国語 → 日本語に翻訳
- 言語は自動判定する

## 口調
- 堅い表現は使わない。フランクな友達口調で
- 台湾華語: 「哈哈」「超好看」「啦」「喔」「欸」「醬」「耶」など台湾の若者のカジュアル表現を自然に使う
- 日本語: 「〜だよ」「〜じゃん」「〜かな」「めっちゃ」「〜よね」など自然な口語

## 文化的ニュアンスの翻訳（重要）
これらは相手に伝わらないので、相手の文化圏の等価表現に変換する:
- 笑/www/草 → 哈哈/XD
- 哈哈/XD → 笑/www
- やばい → 天啊/超扯
- 醬（こういう意味） → そうなんだ/そういうこと
- その他のネットスラング・若者言葉も文化に合わせて自然に変換

## 翻訳不要の判定
以下の場合は「SKIP」とだけ返す:
- 「OK」「Yes」「No」「Thanks」など両言語で通じる単語のみ
- 数字のみ
- URLのみ

## 出力
- 翻訳テキストのみ出力。説明・注釈・引用符は一切不要
- 「SKIP」か翻訳テキストのどちらかだけ返す
"""

client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)


async def translate(text: str) -> str | None:
    """テキストを翻訳する。翻訳不要ならNoneを返す。"""
    response = await client.messages.create(
        model=TRANSLATE_MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
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
