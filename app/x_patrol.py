"""X自動巡回: Grok APIでXを検索し、候補リストを生成する"""

import json
import os
import re
import asyncio
from datetime import datetime
from pathlib import Path

import httpx

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data"))
CHECKED_URLS_FILE = DATA_DIR / "checked-urls.json"

# フィルタリング対象の外部リンクドメイン
QUALITY_DOMAINS = {
    "zenn.dev",
    "note.com",
    "qiita.com",
    "github.com",
    "medium.com",
    "dev.to",
}

# 検索キーワード（英語: バズ投稿限定 / 日本語: 幅広く）
EN_QUERIES = [
    "Claude Code tips",
    "Claude Code workflow",
    "Claude Code MCP",
    "Claude Code hooks",
    "Claude Code skills",
    "AI agent build",
    "prompt engineering techniques",
    "Anthropic API",
]

JA_QUERIES = [
    "Claude Code 設定",
    "Claude Code スキル",
    "AIエージェント 構築",
]


def _load_checked_urls() -> list[str]:
    """既読URLリストを読み込む"""
    if not CHECKED_URLS_FILE.exists():
        return []
    try:
        with open(CHECKED_URLS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[XPatrol] checked-urls.json読み込みエラー: {e}")
        return []


def _save_checked_urls(urls: list[str]):
    """既読URLリストを保存する"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKED_URLS_FILE, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)


def add_to_checked(urls):
    """URLを既読リストに追加する（タスク登録後に呼ぶ）"""
    checked = _load_checked_urls()
    checked_set = set(checked)
    for url in urls:
        if url and url not in checked_set:
            checked.append(url)
            checked_set.add(url)
    _save_checked_urls(checked)


def _parse_grok_response(result: dict) -> list[dict]:
    """Grok APIのレスポンスからX投稿情報を抽出する

    Grokはテキスト形式で結果を返す。フォーマットは以下のいずれか:
    - "1. **@username** ..." （番号リスト）
    - "- **@username**: ..." （箇条書き）
    annotationsにX投稿のURLが含まれる。
    """
    posts = []
    text = ""
    annotations = []

    # output配列からテキストとannotationsを取得
    for item in result.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text += content.get("text", "")
                annotations.extend(content.get("annotations", []))

    if not text:
        return []

    # annotationsからX投稿のURLを抽出
    x_urls = []
    for ann in annotations:
        url = ann.get("url", "")
        if "x.com/" in url or "twitter.com/" in url:
            x_urls.append(url)

    # テキストを投稿ごとに分割
    # パターン1: "- **@username**" (箇条書き)
    # パターン2: "1. **@username**" (番号リスト)
    # パターン3: "**@username**" (太字のみ)
    entries = re.split(r'\n(?=- \*\*@|\d+\.\s+\*\*@)', text)

    url_index = 0
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # ユーザー名を抽出（**@username** または @username パターン）
        author_match = re.search(r'\*\*@(\w+)\*\*|@(\w+)', entry)
        if not author_match:
            continue
        author = author_match.group(1) or author_match.group(2)

        # 投稿テキストを抽出
        # "- **@username**: \"本文\"" や "- **@username** (日時): 本文" 等
        # まずクォート内のテキストを試す
        quote_match = re.search(r'["\u201c](.*?)["\u201d]', entry, re.DOTALL)
        if quote_match:
            post_text = quote_match.group(1)
        else:
            # クォートがなければ、ユーザー名以降のテキスト全体
            post_text = re.sub(r'^[-\d.]*\s*\*\*@\w+\*\*[^:]*:\s*', '', entry)

        # URLアノテーション参照を除去
        post_text = re.sub(r'\[\[\d+\]\]\(https?://[^\)]+\)', '', post_text)
        post_text = post_text.strip()

        # 有用ポイントを抽出
        usefulness = ""
        useful_match = re.search(r'有用ポイント[:：]\s*(.+?)(?:\n|$)', entry)
        if useful_match:
            usefulness = useful_match.group(1).strip()
            # 有用ポイント行をpost_textから除去
            post_text = re.sub(r'有用ポイント[:：]\s*.+?(?:\n|$)', '', post_text).strip()

        # リンク行をpost_textから除去
        post_text = re.sub(r'リンク[:：]\s*.+?(?:\n|$)', '', post_text).strip()

        # このエントリに対応するX URLを取得
        url = x_urls[url_index] if url_index < len(x_urls) else ""
        # annotationsのURLがこのエントリ内に参照されているか確認
        entry_has_url = False
        while url_index < len(x_urls):
            if x_urls[url_index] in entry or url_index == 0:
                url = x_urls[url_index]
                url_index += 1
                entry_has_url = True
                break
            url_index += 1

        if not entry_has_url and url_index < len(x_urls):
            url = x_urls[url_index]
            url_index += 1

        # 外部リンクのドメインを抽出
        link_domains = []
        ext_urls = re.findall(r'https?://([^/\s\)"]+)', entry)
        for domain in ext_urls:
            if 'x.com' not in domain and 'twitter.com' not in domain:
                link_domains.append(domain)

        if post_text or url:
            posts.append({
                "author": author,
                "text": post_text,
                "url": url,
                "usefulness": usefulness,
                "link_domains": link_domains,
                "has_links": len(link_domains) > 0,
                "metrics": {},
            })

    print(f"[XPatrol] パース結果: {len(posts)}件の投稿を抽出")
    return posts


def _build_prompt(query: str, is_english: bool) -> str:
    """検索プロンプトを生成する（英語: バズ限定 / 日本語: 幅広く）"""
    user_context = (
        "The user is a solo entrepreneur running a recruitment agency in Japan, "
        "heavily using Claude Code for business automation. "
        "Posts are valuable if they contain: practical tool configs, "
        "comparisons, templates/frameworks, security tips, or links to "
        "in-depth articles (Zenn, note, Qiita, GitHub, Medium, dev.to)."
    )

    if is_english:
        return (
            f"Search X/Twitter for recent posts (last 24 hours) about: {query}\n\n"
            f"CONTEXT: {user_context}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "1. Return ONLY the top 3 VIRAL/HIGH-ENGAGEMENT posts\n"
            "   - Must have at least 100+ likes or significant reposts\n"
            "   - Ignore low-engagement posts even if content seems good\n"
            "2. SKIP these types:\n"
            "   - Short reactions, hype posts ('amazing!', 'this is huge!')\n"
            "   - Promotional spam, follower-bait, course/product sales\n"
            "   - Posts that just share a link without explanation\n"
            "3. PRIORITIZE:\n"
            "   - Practical tutorials, workflows, configs with real examples\n"
            "   - Tool comparisons with concrete benchmarks/numbers\n"
            "   - Framework/template introductions\n"
            "   - Security/architecture best practices\n"
            "   - Links to detailed articles or GitHub repos\n"
            "4. For EACH post, respond in this EXACT format:\n"
            "   1. **@username**: [完全な日本語訳（全文を自然な日本語に翻訳）]\n"
            "   有用ポイント: [人材紹介×AI活用の個人事業主にとって価値がある理由を1行で]\n"
            "   リンク: [外部リンクがあれば記載]\n"
            "5. ALL text must be in Japanese\n"
        )
    else:
        return (
            f"X/Twitterで直近24時間の投稿を検索: {query}\n\n"
            f"CONTEXT: {user_context}\n\n"
            "指示:\n"
            "1. 有用な投稿を3-5件返してください（エンゲージメントの高さは必須条件ではない）\n"
            "2. スキップすべき投稿:\n"
            "   - 短い感想・反応だけ（『すごい！』『神！』）\n"
            "   - 宣伝・セルフプロモーション\n"
            "   - リンクだけで説明なし\n"
            "3. 優先すべき投稿:\n"
            "   - 実用的な設定方法・ワークフロー・Tips\n"
            "   - ツール比較・レビュー\n"
            "   - 詳細記事へのリンク付き（Zenn, note, Qiita, GitHub等）\n"
            "   - セキュリティ・設計のベストプラクティス\n"
            "4. 各投稿を以下の形式で回答:\n"
            "   1. **@username**: [投稿の全文]\n"
            "   有用ポイント: [人材紹介×AI活用の個人事業主にとって価値がある理由を1行で]\n"
            "   リンク: [外部リンクがあれば記載]\n"
        )


async def search_x(query: str, api_key: str, is_english: bool = True) -> list[dict]:
    """Grok APIでXを検索し、投稿リストを返す"""
    lang_label = "EN" if is_english else "JA"
    print(f"[XPatrol] [{lang_label}] 検索中: {query}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.x.ai/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-4-1-fast-reasoning",
                    "input": _build_prompt(query, is_english),
                    "tools": [{"type": "x_search"}],
                },
                timeout=120.0,
            )
            result = response.json()
        except httpx.TimeoutException:
            print(f"[XPatrol] タイムアウト: {query}")
            return []
        except Exception as e:
            print(f"[XPatrol] API呼び出しエラー ({query}): {e}")
            return []

    # エラーチェック
    if isinstance(result, dict) and result.get("error"):
        print(f"[XPatrol] APIエラー ({query}): {result['error']}")
        return []

    posts = _parse_grok_response(result)
    print(f"[XPatrol] '{query}' → {len(posts)}件取得")
    return posts


def _is_quality_post(post: dict) -> bool:
    """フィルタリングロジック: 候補に残すかどうか判定する"""
    # URLがない投稿は除外
    if not post.get("url", ""):
        return False

    text = post.get("text", "")

    # テキストが空の投稿は除外
    if not text.strip():
        return False

    # Grokが厳選しているのでテキストがあればOK
    return True


def _normalize_x_url(url: str) -> str:
    """X投稿URLを正規化する（/i/status/xxx と /user/status/xxx を同一視）"""
    # status IDを抽出
    match = re.search(r'/status/(\d+)', url)
    if match:
        return match.group(1)
    return url


def _deduplicate_by_url(posts: list[dict]) -> list[dict]:
    """同一投稿の重複排除（URLのstatus IDで判定 + テキスト類似度）"""
    seen_ids = set()
    seen_texts = set()
    unique_posts = []

    for post in posts:
        url = post.get("url", "")
        text = post.get("text", "")

        # URL正規化で重複チェック
        if url:
            normalized = _normalize_x_url(url)
            if normalized in seen_ids:
                continue
            seen_ids.add(normalized)

        # テキスト先頭100文字で重複チェック（同じ内容の別URL対策）
        text_key = text[:100].strip()
        if text_key and text_key in seen_texts:
            continue
        if text_key:
            seen_texts.add(text_key)

        unique_posts.append(post)

    return unique_posts


def _filter_candidates(posts: list[dict], checked_urls: list[str]) -> list[dict]:
    """全フィルタリングを適用して候補リストを返す"""
    checked_set = set(checked_urls)

    # 品質フィルタ
    quality_posts = [p for p in posts if _is_quality_post(p)]

    # 重複排除
    deduped = _deduplicate_by_url(quality_posts)

    # 既読除外
    new_posts = [p for p in deduped if p.get("url", "") not in checked_set]

    return new_posts


async def run_patrol(api_key: str) -> list[dict]:
    """全キーワードを巡回して候補リストを返す"""
    if not api_key:
        print("[XPatrol] XAI_API_KEYが設定されていません")
        return []

    checked_urls = _load_checked_urls()
    all_posts = []

    # 英語キーワード（バズ投稿限定）
    for query in EN_QUERIES:
        posts = await search_x(query, api_key, is_english=True)
        all_posts.extend(posts)
        await asyncio.sleep(2)

    # 日本語キーワード（幅広く）
    for query in JA_QUERIES:
        posts = await search_x(query, api_key, is_english=False)
        all_posts.extend(posts)
        await asyncio.sleep(2)

    # フィルタリング
    candidates = _filter_candidates(all_posts, checked_urls)
    print(f"[XPatrol] 巡回完了: 全{len(all_posts)}件 → 候補{len(candidates)}件")
    return candidates
