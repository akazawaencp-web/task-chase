"""URL内容取得: URLからOGPタイトル・説明を自動取得する"""

import re
import httpx


# URLを検出する正規表現
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# YouTube URL判定
YOUTUBE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})'
)

# X / Twitter URL判定
X_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/(\d+)'
)


def extract_urls(text: str) -> list[str]:
    """テキストからURLを抽出"""
    return URL_PATTERN.findall(text)


async def _fetch_youtube_metadata(video_id: str, timeout: float = 8.0) -> dict:
    """YouTube oEmbed APIで動画タイトルを取得（APIキー不要）"""
    result = {"title": "", "description": ""}
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(oembed_url)
            if resp.status_code == 200:
                data = resp.json()
                result["title"] = data.get("title", "")
                result["description"] = f'YouTube動画（投稿者: {data.get("author_name", "")}）'
    except Exception as e:
        print(f"[URLFetch] YouTube oEmbed エラー: {e}")
    return result


async def _fetch_x_metadata(tweet_id: str, timeout: float = 8.0) -> dict:
    """FxTwitter APIでX投稿の本文を取得（APIキー不要）"""
    result = {"title": "", "description": ""}
    fx_url = f"https://api.fxtwitter.com/i/status/{tweet_id}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(fx_url)
            if resp.status_code == 200:
                data = resp.json()
                tweet = data.get("tweet", {})
                text = tweet.get("text", "")
                author = tweet.get("author", {}).get("name", "")
                if text:
                    # 先頭60文字をタイトルに
                    result["title"] = text[:60].replace("\n", " ") + ("…" if len(text) > 60 else "")
                    result["description"] = f'X投稿（@{tweet.get("author", {}).get("screen_name", "")} / {author}）'
    except Exception as e:
        print(f"[URLFetch] FxTwitter APIエラー: {e}")
    return result


async def fetch_url_metadata(url: str, timeout: float = 8.0) -> dict:
    """URLのタイトル・説明を取得（YouTube/X/その他を自動判別）"""
    result = {"url": url, "title": "", "description": ""}

    # YouTube URL
    yt_match = YOUTUBE_PATTERN.search(url)
    if yt_match:
        meta = await _fetch_youtube_metadata(yt_match.group(1), timeout)
        result.update(meta)
        return result

    # X / Twitter URL
    x_match = X_PATTERN.search(url)
    if x_match:
        meta = await _fetch_x_metadata(x_match.group(1), timeout)
        result.update(meta)
        return result

    # その他：OGP / HTMLタグから取得
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TaskChaseBot/1.0)"}
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return result

            html = resp.text[:50000]  # 先頭50KBだけ解析

            # OGP title
            og_title = _extract_meta(html, 'og:title')
            if og_title:
                result["title"] = og_title

            # OGP description
            og_desc = _extract_meta(html, 'og:description')
            if og_desc:
                result["description"] = og_desc

            # fallback: <title>タグ
            if not result["title"]:
                title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
                if title_match:
                    result["title"] = _clean_html(title_match.group(1)).strip()

            # fallback: meta description
            if not result["description"]:
                desc = _extract_meta_name(html, 'description')
                if desc:
                    result["description"] = desc

    except Exception as e:
        print(f"[URLFetch] {url} 取得エラー: {type(e).__name__}: {e}")

    return result


def _extract_meta(html: str, property_name: str) -> str:
    """OGPメタタグの値を取得"""
    pattern = re.compile(
        r'<meta\s+[^>]*property=["\']' + re.escape(property_name) + r'["\'][^>]*content=["\']([^"\']*)["\']',
        re.IGNORECASE
    )
    match = pattern.search(html)
    if match:
        return _clean_html(match.group(1))

    # content が先に来るパターン
    pattern2 = re.compile(
        r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']' + re.escape(property_name) + r'["\']',
        re.IGNORECASE
    )
    match2 = pattern2.search(html)
    if match2:
        return _clean_html(match2.group(1))

    return ""


def _extract_meta_name(html: str, name: str) -> str:
    """name属性のメタタグの値を取得"""
    pattern = re.compile(
        r'<meta\s+[^>]*name=["\']' + re.escape(name) + r'["\'][^>]*content=["\']([^"\']*)["\']',
        re.IGNORECASE
    )
    match = pattern.search(html)
    if match:
        return _clean_html(match.group(1))

    pattern2 = re.compile(
        r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']' + re.escape(name) + r'["\']',
        re.IGNORECASE
    )
    match2 = pattern2.search(html)
    if match2:
        return _clean_html(match2.group(1))

    return ""


def _clean_html(text: str) -> str:
    """HTMLエンティティを変換"""
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&#x27;', "'")
    text = text.replace('\n', ' ').replace('\r', '')
    return text.strip()
