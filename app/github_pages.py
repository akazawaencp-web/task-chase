"""GitHub Pages: 生成したHTMLをリポジトリにpushして公開する"""

import subprocess
from pathlib import Path
from app.config import Config

REPO_DIR = Path(__file__).parent.parent
REPORTS_DIR = REPO_DIR / "reports"


def publish_report(html_filepath: str) -> str:
    """HTMLファイルをGitHub Pagesにデプロイし、公開URLを返す"""

    filepath = Path(html_filepath)
    filename = filepath.name

    # git add → commit → push
    try:
        subprocess.run(
            ["git", "add", str(filepath.relative_to(REPO_DIR))],
            cwd=str(REPO_DIR),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add report: {filename}"],
            cwd=str(REPO_DIR),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push"],
            cwd=str(REPO_DIR),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        return ""

    # 公開URL
    url = f"{Config.GITHUB_PAGES_URL}/reports/{filename}"
    return url
