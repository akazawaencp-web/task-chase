"""URL内容取得: URLからOGPタイトル・説明を自動取得する"""

import re
import httpx


# URLを検出する正規表現
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls(text: str) -> list[str]:
    """テキストからURLを抽出"""
    return URL_PATTERN.findall(text)


async def fetch_url_metadata(url: str, timeout: float = 8.0) -> dict:
    """URLのOGPタイトル・説明を取得"""
    result = {"url": url, "title": "", "description": ""}

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
