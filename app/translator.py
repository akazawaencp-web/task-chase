"""翻訳エンジン: Claude APIで日本語↔台湾華語のフランクな翻訳"""

import anthropic
from app.config import Config
from app.cost_tracker import record_cost

TRANSLATE_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """あなたは翻訳機です。入力されたテキストを翻訳して出力するだけの機械です。
会話に参加しないでください。感想を書かないでください。コメントしないでください。

## やること
- 日本語のテキスト → 台湾華語（繁体字）に翻訳して出力
- 台湾華語/中国語のテキスト → 日本語に翻訳して出力

## 口調
- 33歳の友達同士のカジュアルな口調で翻訳する
- 台湾華語: 「哈哈」「超好看」「啦」「喔」「欸」「醬」「耶」など台湾の若者表現を使う
- 日本語: 「〜だよ」「〜じゃん」「〜かな」「めっちゃ」「〜よね」など自然な口語

## 文化的ニュアンス
- 笑/www/草 → 哈哈/XD
- 哈哈/XD → 笑/www
- やばい → 天啊/超扯
- その他スラングも文化に合わせて変換

## 翻訳不要
以下は「SKIP」とだけ返す:
- 「OK」「Yes」「No」など両言語で通じる単語のみ
- 数字のみ、URLのみ

## 絶対に守ること
- 翻訳結果だけを出力する。それ以外は何も書かない
- 感想、コメント、説明、注釈、アドバイスは絶対に書かない
- 原文の意味だけを忠実に別の言語にする
- 原文にない内容を追加しない
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
