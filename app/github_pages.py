"""レポート公開: 生成したHTMLの公開URLを返す"""

import os
from pathlib import Path


def publish_report(html_filepath: str) -> str:
    """HTMLファイルの公開URLを返す（FastAPIの静的ファイル配信を利用）"""

    filepath = Path(html_filepath)
    filename = filepath.name

    # Railway上のドメインを環境変数から取得、なければデフォルト
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    if domain:
        return f"https://{domain}/reports/{filename}"

    # ローカル開発用
    port = os.getenv("PORT", "8000")
    return f"http://localhost:{port}/reports/{filename}"
