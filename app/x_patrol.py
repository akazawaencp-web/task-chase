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

# 検索キーワード（英語8個 + 日本語3個）
SEARCH_QUERIES = [
    "Claude Code tips",
    "Claude Code workflow",
    "Claude Code MCP",
    "Claude Code hooks",
    "Claude Code skills",
    "AI agent build",
    "prompt engineering techniques",
    "Anthropic API",
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

    Grokはテキスト形式で結果を返し、URLはannotationsに含まれる。
    テキストからアカウント名・投稿内容を、annotationsからURLを抽出する。
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

    # テキストを投稿ごとに分割（番号パターンで区切り）
    # "1. **@username**" や "1." のパターンで分割
    entries = re.split(r'\n\d+\.\s+', text)

    for i, entry in enumerate(entries):
        if not entry.strip():
            continue

        # ユーザー名を抽出（**@username** パターン）
        author_match = re.search(r'@(\w+)', entry)
        author = author_match.group(1) if author_match else "unknown"

        # 投稿テキストを抽出（ユーザー名・日時行以降の本文）
        # 改行で分割して、本文部分を結合
        lines = entry.strip().split('\n')
        post_text_lines = []
        for line in lines:
            line = line.strip()
            # メタ情報行をスキップ
            if line.startswith('**@') or line.startswith('(') or not line:
                continue
            # URLアノテーションの参照を除去
            line = re.sub(r'\[\[\d+\]\]\(https?://[^\)]+\)', '', line)
            if line:
                post_text_lines.append(line)
        post_text = '\n'.join(post_text_lines)

        # このエントリに対応するURLを取得
        url = x_urls[i - 1] if 0 < i <= len(x_urls) else ""

        # 外部リンクのドメインを抽出
        link_domains = []
        ext_urls = re.findall(r'https?://([^/\s\)]+)', entry)
        for domain in ext_urls:
            if 'x.com' not in domain and 'twitter.com' not in domain:
                # サブドメインを含む形で記録
                link_domains.append(domain)

        if post_text or url:
            posts.append({
                "author": author,
                "text": post_text,
                "url": url,
                "link_domains": link_domains,
                "has_links": len(link_domains) > 0,
                "metrics": {},
            })

    print(f"[XPatrol] パース結果: {len(posts)}件の投稿を抽出")
    return posts


async def search_x(query: str, api_key: str) -> list[dict]:
    """Grok APIでXを検索し、投稿リストを返す"""
    print(f"[XPatrol] 検索中: {query}")
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
                    "input": (
                        f"Search X/Twitter for recent posts (last 24 hours) about: {query}\n\n"
                        "List each post with the author's @username, the full post text, "
                        "and any external links mentioned in the post. "
                        "Include as many relevant posts as you can find from the last 24 hours."
                    ),
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
    text = post.get("text", "")
    link_domains = post.get("link_domains", [])

    # 200文字以上 → 候補
    if len(text) >= 200:
        return True

    # 200文字未満でも品質ドメインへのリンクがある → 候補
    for domain in link_domains:
        for qd in QUALITY_DOMAINS:
            if qd in domain:
                return True

    # 200文字未満でも外部リンクがある → 候補（記事付き投稿）
    if post.get("has_links"):
        return True

    return False


def _deduplicate_by_url(posts: list[dict]) -> list[dict]:
    """同一URLを引用している投稿の重複排除"""
    seen_urls = set()
    unique_posts = []

    for post in posts:
        url = post.get("url", "")
        if not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
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

    # 各キーワードを順番に検索
    for query in SEARCH_QUERIES:
        posts = await search_x(query, api_key)
        all_posts.extend(posts)
        # APIレート制限を考慮して少し待つ
        await asyncio.sleep(2)

    # フィルタリング
    candidates = _filter_candidates(all_posts, checked_urls)
    print(f"[XPatrol] 巡回完了: 全{len(all_posts)}件 → 候補{len(candidates)}件")
    return candidates
