#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X(Twitter)の投稿内容をFxTwitter API経由で取得するスクリプト。
APIキー不要・無料で、投稿のテキスト・画像・動画・記事・引用ツイートを取得できる。

使い方:
  python3 fetch_x_post.py "https://x.com/user/status/123456789"
  python3 fetch_x_post.py "https://x.com/user/status/123456789" --json

出力:
  デフォルト: 人間が読める形式のテキスト
  --json: 構造化されたJSONデータ
"""

import json
import re
import subprocess
import sys


def parse_x_url(url):
    """XのURLからユーザー名とステータスIDを抽出"""
    patterns = [
        r'(?:twitter\.com|x\.com)/(\w+)/status/(\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1), m.group(2)
    return None, None


def fetch_via_fxtwitter(username, status_id):
    """FxTwitter APIで投稿データを取得"""
    api_url = f"https://api.fxtwitter.com/{username}/status/{status_id}"
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", api_url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None


def fetch_via_syndication(status_id):
    """Syndication API（バックアップ）で投稿データを取得"""
    api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={status_id}&token=x"
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", api_url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None


def extract_article_text(article):
    """X記事機能のコンテンツブロックからテキストを抽出"""
    if not article or "content" not in article:
        return ""

    blocks = article["content"].get("blocks", [])
    lines = []
    for b in blocks:
        btype = b.get("type", "unstyled")
        text = b.get("text", "")

        if btype.startswith("header"):
            lines.append(f"\n## {text}")
        elif btype == "ordered-list-item":
            lines.append(f"  - {text}")
        elif btype == "unordered-list-item":
            lines.append(f"  * {text}")
        elif btype == "atomic":
            # メディアやリンクのエンティティ
            pass
        else:
            if text:
                lines.append(text)

    return "\n".join(lines)


def format_fxtwitter(data):
    """FxTwitterのレスポンスを構造化データに変換"""
    tweet = data.get("tweet", {})
    author = tweet.get("author", {})

    result = {
        "ok": True,
        "source": "fxtwitter",
        "author_name": author.get("name", ""),
        "author_screen_name": author.get("screen_name", ""),
        "author_description": author.get("description", ""),
        "author_followers": author.get("followers", 0),
        "text": tweet.get("text", ""),
        "created_at": tweet.get("created_at", ""),
        "likes": tweet.get("likes", 0),
        "retweets": tweet.get("retweets", 0),
        "replies": tweet.get("replies", 0),
        "views": tweet.get("views", 0),
        "bookmarks": tweet.get("bookmarks", 0),
        "url": tweet.get("url", ""),
        "media": [],
        "article_title": "",
        "article_text": "",
        "quote_tweet": None,
        "embedded_urls": [],
    }

    # メディア（画像・動画）
    media = tweet.get("media", {})
    if media:
        for m in media.get("all", []):
            mtype = m.get("type", "")
            item = {"type": mtype}
            if mtype == "photo":
                item["url"] = m.get("url", "")
                item["alt_text"] = m.get("altText", "")
            elif mtype in ("video", "gif"):
                item["url"] = m.get("url", "")
                item["thumbnail"] = m.get("thumbnail_url", "")
                item["duration"] = m.get("duration", 0)
            result["media"].append(item)

    # 記事（X記事機能）
    article = tweet.get("article")
    if article:
        result["article_title"] = article.get("title", "")
        result["article_text"] = extract_article_text(article)

    # 引用ツイート
    qt = tweet.get("quote")
    if qt:
        qt_author = qt.get("author", {})
        result["quote_tweet"] = {
            "author_name": qt_author.get("name", ""),
            "author_screen_name": qt_author.get("screen_name", ""),
            "text": qt.get("text", ""),
            "url": qt.get("url", ""),
        }

    # 埋め込みURL（t.coリンク）
    raw_text = tweet.get("raw_text", {}).get("text", "")
    urls = re.findall(r'https?://t\.co/\w+', raw_text)
    if urls:
        result["embedded_urls"] = urls

    return result


def format_syndication(data):
    """Syndication APIのレスポンスを構造化データに変換"""
    user = data.get("user", {})
    result = {
        "ok": True,
        "source": "syndication",
        "author_name": user.get("name", ""),
        "author_screen_name": user.get("screen_name", ""),
        "text": data.get("text", ""),
        "created_at": data.get("created_at", ""),
        "likes": data.get("favorite_count", 0),
        "retweets": 0,
        "replies": 0,
        "views": 0,
        "bookmarks": 0,
        "url": "",
        "media": [],
        "article_title": "",
        "article_text": "",
        "quote_tweet": None,
        "embedded_urls": [],
    }

    # メディア
    for m in data.get("mediaDetails", []):
        mtype = m.get("type", "")
        item = {"type": mtype}
        if mtype == "photo":
            item["url"] = m.get("media_url_https", "")
        elif mtype == "video":
            variants = m.get("video_info", {}).get("variants", [])
            mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
            if mp4s:
                best = max(mp4s, key=lambda v: v.get("bitrate", 0))
                item["url"] = best.get("url", "")
        result["media"].append(item)

    return result


def to_human_readable(data):
    """構造化データを人間が読める日本語テキストに変換"""
    lines = []
    lines.append(f"投稿者: {data['author_name']} (@{data['author_screen_name']})")
    lines.append(f"投稿日時: {data['created_at']}")
    stats = []
    if data["likes"]:
        stats.append(f"いいね {data['likes']}")
    if data["retweets"]:
        stats.append(f"RT {data['retweets']}")
    if data["views"]:
        stats.append(f"閲覧 {data['views']:,}")
    if data["bookmarks"]:
        stats.append(f"ブックマーク {data['bookmarks']}")
    if stats:
        lines.append(f"反応: {' / '.join(stats)}")
    lines.append("")

    # 記事がある場合
    if data["article_title"]:
        lines.append(f"=== 記事: {data['article_title']} ===")
        lines.append("")
        lines.append(data["article_text"])
        lines.append("")
    elif data["text"]:
        lines.append(f"本文:")
        lines.append(data["text"])
        lines.append("")

    # メディア
    if data["media"]:
        lines.append(f"メディア ({len(data['media'])}件):")
        for m in data["media"]:
            if m["type"] == "photo":
                alt = f" ({m.get('alt_text', '')})" if m.get("alt_text") else ""
                lines.append(f"  [画像{alt}] {m.get('url', '')}")
            elif m["type"] in ("video", "gif"):
                dur = m.get("duration", 0)
                dur_str = f" ({dur}秒)" if dur else ""
                lines.append(f"  [動画{dur_str}] {m.get('url', '')}")
        lines.append("")

    # 引用ツイート
    if data["quote_tweet"]:
        qt = data["quote_tweet"]
        lines.append(f"引用ツイート:")
        lines.append(f"  {qt['author_name']} (@{qt['author_screen_name']})")
        lines.append(f"  {qt['text']}")
        lines.append("")

    # 埋め込みURL
    if data["embedded_urls"]:
        lines.append(f"埋め込みURL:")
        for u in data["embedded_urls"]:
            lines.append(f"  {u}")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("X(Twitter)の投稿を取得するスクリプト（FxTwitter API使用、無料・キー不要）", file=sys.stderr)
        print("", file=sys.stderr)
        print("使い方:", file=sys.stderr)
        print('  python3 fetch_x_post.py "https://x.com/user/status/123"', file=sys.stderr)
        print('  python3 fetch_x_post.py "https://x.com/user/status/123" --json', file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    output_json = "--json" in sys.argv

    username, status_id = parse_x_url(url)
    if not username or not status_id:
        print(f"エラー: X(Twitter)のURLを認識できません: {url}", file=sys.stderr)
        sys.exit(1)

    # FxTwitter API（メイン）
    raw = fetch_via_fxtwitter(username, status_id)
    if raw and raw.get("tweet"):
        data = format_fxtwitter(raw)
    else:
        # Syndication API（バックアップ）
        raw = fetch_via_syndication(status_id)
        if raw and raw.get("text"):
            data = format_syndication(raw)
        else:
            print("エラー: 投稿を取得できませんでした。URLが正しいか確認してください。", file=sys.stderr)
            sys.exit(1)

    if output_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(to_human_readable(data))


if __name__ == "__main__":
    main()
