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


def _extract_json_array(text: str) -> list[dict]:
    """テキスト内からJSON配列部分を抽出してパースする"""
    # [...] 形式のJSONを正規表現で抽出
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[XPatrol] JSONパースエラー: {e}")
        return []


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
                    "model": "grok-3-mini",
                    "input": (
                        f"Search X/Twitter for recent posts (last 24 hours) about: {query}\n\n"
                        "Return the results as a JSON array. Each item should have: "
                        "author (username), text (full post text), url (post URL), "
                        "metrics (likes, retweets, impressions if available), "
                        "has_links (boolean, true if post contains external URLs), "
                        "link_domains (list of external link domains like zenn.dev, note.com, etc). "
                        "Only include posts from the last 24 hours. "
                        "Return ONLY valid JSON, no other text."
                    ),
                    "tools": [{"type": "x_search"}],
                },
                timeout=60.0,
            )
            result = response.json()
        except httpx.TimeoutException:
            print(f"[XPatrol] タイムアウト: {query}")
            return []
        except Exception as e:
            print(f"[XPatrol] API呼び出しエラー ({query}): {e}")
            return []

    # レスポンスからテキスト部分を抽出
    raw_text = ""
    if isinstance(result, dict):
        # output配列の中からテキストを探す
        for item in result.get("output", []):
            if isinstance(item, dict):
                for content in item.get("content", []):
                    if isinstance(content, dict) and content.get("type") == "output_text":
                        raw_text += content.get("text", "")
        # フォールバック: 直接textフィールド
        if not raw_text:
            raw_text = str(result)

    posts = _extract_json_array(raw_text)
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
        if domain in QUALITY_DOMAINS:
            return True

    return False


def _deduplicate_by_url(posts: list[dict]) -> list[dict]:
    """同一URLを引用している投稿の重複排除（最高インプレッションのみ残す）"""
    # URLをキーに、最高インプレッションの投稿を保持
    url_best: dict[str, dict] = {}

    for post in posts:
        url = post.get("url", "")
        if not url:
            continue

        # メトリクスからインプレッションを取得
        metrics = post.get("metrics", {})
        if isinstance(metrics, dict):
            impressions = metrics.get("impressions", 0) or 0
        else:
            impressions = 0

        if url not in url_best:
            url_best[url] = {"post": post, "impressions": impressions}
        elif impressions > url_best[url]["impressions"]:
            url_best[url] = {"post": post, "impressions": impressions}

    return [v["post"] for v in url_best.values()]


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
        await asyncio.sleep(1)

    # フィルタリング
    candidates = _filter_candidates(all_posts, checked_urls)
    print(f"[XPatrol] 巡回完了: 全{len(all_posts)}件 → 候補{len(candidates)}件")
    return candidates
