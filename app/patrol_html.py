"""X巡回レポートHTML生成: チェックボックス付き候補一覧ページを作成する"""

import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data"))
REPORTS_DIR = DATA_DIR / "reports"


def _detect_language(post: dict) -> str:
    """投稿テキストの言語を簡易判定（日本語文字が含まれればJP）"""
    text = post.get("text", "")
    for char in text:
        if "\u3000" <= char <= "\u9fff" or "\uff00" <= char <= "\uffef":
            return "JP"
    return "EN"


def _build_candidate_html(post: dict, index: int) -> str:
    """1件分の候補カードHTMLを生成する"""
    author = post.get("author", "不明")
    text = post.get("text", "")
    url = post.get("url", "")
    link_domains = post.get("link_domains", [])
    lang = _detect_language(post)

    # テキストは冒頭200文字に切り詰め
    preview = text[:200] + ("..." if len(text) > 200 else "")
    # HTML特殊文字をエスケープ
    preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    author_escaped = author.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    url_escaped = url.replace('"', "&quot;")

    # 外部リンクドメインのタグ
    domain_tags = ""
    for domain in link_domains[:3]:  # 最大3件まで表示
        domain_escaped = domain.replace("&", "&amp;")
        domain_tags += f'<span class="domain-tag">{domain_escaped}</span>'

    lang_class = "lang-jp" if lang == "JP" else "lang-en"

    return f"""
  <div class="candidate-card" id="card-{index}">
    <label class="card-label">
      <input
        type="checkbox"
        class="candidate-check"
        value="{index}"
        data-url="{url_escaped}"
        data-text="{preview.replace(chr(34), '&quot;')}"
        data-author="{author_escaped}"
      >
      <div class="card-body">
        <div class="card-meta">
          <span class="author">@{author_escaped}</span>
          <span class="lang-badge {lang_class}">{lang}</span>
        </div>
        <div class="card-text">{preview}</div>
        {f'<div class="domain-list">{domain_tags}</div>' if domain_tags else ""}
        <a class="post-link" href="{url_escaped}" target="_blank" rel="noopener">投稿を見る</a>
      </div>
    </label>
  </div>"""


def generate_patrol_html(candidates: list[dict], date_str: str = "") -> str:
    """巡回レポートHTMLを生成してファイルパスを返す"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    filename = f"patrol-{date_str}.html"
    filepath = REPORTS_DIR / filename

    today_display = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    count = len(candidates)

    # 候補カードのHTML生成
    if count == 0:
        candidates_html = '<div class="empty-state">今日の候補はありませんでした</div>'
        submit_section = ""
    else:
        cards = "".join(_build_candidate_html(p, i) for i, p in enumerate(candidates))
        candidates_html = cards
        submit_section = """
<div class="submit-section">
  <div class="pin-row">
    <label class="pin-label" for="pin-input">PIN（4桁）</label>
    <input type="password" id="pin-input" maxlength="4" inputmode="numeric" pattern="[0-9]{4}" placeholder="----" class="pin-input">
  </div>
  <button class="submit-btn" onclick="submitSelections()">深掘り開始</button>
  <div id="result-msg" class="result-msg" style="display:none;"></div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>X自動巡回レポート — {today_display}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Sans:wght@400;500;600;700&family=BIZ+UDPGothic:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {{
  --coral: #ea8768;
  --coral-light: rgba(234,135,104,.08);
  --coral-mid: rgba(234,135,104,.15);
  --sky: #33b6de;
  --sky-light: rgba(51,182,222,.08);
  --sky-mid: rgba(51,182,222,.15);
  --bg: #f5f5f7;
  --tx: #1a1a2e;
  --tx2: #6b7280;
  --tx3: #9ca3af;
  --bd: #e5e7eb;
  --ok: #22c55e;
  --shimmer: linear-gradient(145deg, #fff 0%, #fafafc 22%, #fff 45%, #f7f7fb 68%, #fff 88%, #fbfbfe 100%);
  --sh: 0 1px 3px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.06);
  --sh2: 0 2px 6px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.08);
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', 'BIZ UDPGothic', sans-serif;
  background: transparent;
  color: var(--tx);
  line-height: 1.6;
  padding: 24px 16px 48px;
  max-width: 720px;
  margin: 0 auto;
  position: relative;
  z-index: 10;
}}
#bg-canvas {{
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  z-index: 0;
  pointer-events: none;
}}
#bg-grain {{
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.7' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E");
  mix-blend-mode: multiply;
}}
.content-wrap {{
  position: relative;
  z-index: 10;
}}
/* ヘッダー */
.page-header {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh2);
  padding: 24px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.page-header::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--coral), var(--sky));
}}
.page-title {{
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -.02em;
  margin-bottom: 6px;
}}
.page-meta {{
  font-size: 12px;
  color: var(--tx2);
}}
.count-badge {{
  display: inline-block;
  background: var(--coral-light);
  color: var(--coral);
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 99px;
  margin-left: 8px;
}}
/* 候補カード */
.candidate-card {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
  transition: box-shadow .15s;
}}
.candidate-card::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--sky);
  transition: background .15s;
}}
.candidate-card:has(.candidate-check:checked)::before {{
  background: var(--coral);
}}
.candidate-card:has(.candidate-check:checked) {{
  box-shadow: var(--sh2);
}}
.card-label {{
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 20px;
  cursor: pointer;
}}
.candidate-check {{
  width: 20px;
  height: 20px;
  accent-color: var(--coral);
  flex-shrink: 0;
  margin-top: 2px;
}}
.card-body {{
  flex: 1;
  min-width: 0;
}}
.card-meta {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}}
.author {{
  font-size: 12px;
  font-weight: 600;
  color: var(--sky);
}}
.lang-badge {{
  font-size: 9px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 99px;
  letter-spacing: .06em;
}}
.lang-en {{
  background: var(--coral-light);
  color: var(--coral);
}}
.lang-jp {{
  background: var(--sky-light);
  color: var(--sky);
}}
.card-text {{
  font-size: 13px;
  color: var(--tx);
  line-height: 1.6;
  margin-bottom: 8px;
  word-break: break-all;
}}
.domain-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}}
.domain-tag {{
  font-size: 10px;
  font-weight: 500;
  background: rgba(34,197,94,.08);
  color: var(--ok);
  padding: 2px 8px;
  border-radius: 99px;
}}
.post-link {{
  font-size: 11px;
  color: var(--tx3);
  text-decoration: none;
}}
.post-link:hover {{
  color: var(--sky);
  text-decoration: underline;
}}
/* 空状態 */
.empty-state {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  padding: 40px 28px;
  text-align: center;
  color: var(--tx2);
  font-size: 14px;
  position: relative;
  overflow: hidden;
}}
.empty-state::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--bd);
}}
/* 送信エリア */
.submit-section {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh2);
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
  margin-top: 24px;
}}
.submit-section::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--coral);
}}
.pin-row {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}}
.pin-label {{
  font-size: 12px;
  font-weight: 600;
  color: var(--tx2);
  white-space: nowrap;
}}
.pin-input {{
  font-family: 'DM Sans', monospace;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: .15em;
  width: 100px;
  border: 1.5px solid var(--bd);
  border-radius: 8px;
  padding: 6px 12px;
  background: #fff;
  color: var(--tx);
  outline: none;
  transition: border-color .15s;
}}
.pin-input:focus {{
  border-color: var(--coral);
}}
.submit-btn {{
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, var(--coral), #d4724f);
  color: #fff;
  font-family: inherit;
  font-size: 15px;
  font-weight: 700;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  letter-spacing: .02em;
  transition: opacity .15s;
}}
.submit-btn:hover {{ opacity: .85; }}
.submit-btn:active {{ opacity: .7; }}
.submit-btn:disabled {{
  background: var(--bd);
  color: var(--tx3);
  cursor: not-allowed;
  opacity: 1;
}}
.result-msg {{
  margin-top: 14px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
}}
.result-msg.success {{
  background: rgba(34,197,94,.08);
  color: var(--ok);
}}
.result-msg.error {{
  background: rgba(239,68,68,.06);
  color: #ef4444;
}}
/* フッター */
.page-footer {{
  text-align: center;
  padding: 24px 0 8px;
  font-size: 10px;
  color: var(--tx3);
}}
@media (max-width: 480px) {{
  .page-title {{ font-size: 17px; }}
  .card-label {{ gap: 10px; padding: 14px 16px; }}
}}
</style>
</head>
<body>
<canvas id="bg-canvas"></canvas>
<div id="bg-grain"></div>
<div class="content-wrap">

<div class="page-header">
  <div class="page-title">
    X自動巡回レポート
    {f'<span class="count-badge">{count}件</span>' if count > 0 else ""}
  </div>
  <div class="page-meta">{today_display} &nbsp;|&nbsp; Claude Code / AI関連投稿の自動収集</div>
</div>

{candidates_html}

{submit_section}

<div class="page-footer">Task Chase System — X Patrol {today_display}</div>

</div>

<script>
async function submitSelections() {{
  const pin = document.getElementById('pin-input').value.trim();
  if (pin.length !== 4) {{
    showResult('PINは4桁で入力してください', 'error');
    return;
  }}

  const checks = document.querySelectorAll('.candidate-check:checked');
  if (checks.length === 0) {{
    showResult('候補を1件以上選択してください', 'error');
    return;
  }}

  // チェックされた候補の情報を収集
  const selected = Array.from(checks).map(cb => ({{
    url: cb.dataset.url,
    text: cb.dataset.text,
    title: 'X投稿深掘り: @' + cb.dataset.author,
  }}));

  const btn = document.querySelector('.submit-btn');
  btn.disabled = true;
  btn.textContent = '送信中...';

  try {{
    const res = await fetch('/api/patrol/submit', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ pin, selected }}),
    }});
    const data = await res.json();

    if (data.error) {{
      showResult(data.error, 'error');
      btn.disabled = false;
      btn.textContent = '深掘り開始';
    }} else {{
      showResult(data.message || '登録完了！', 'success');
      btn.textContent = '送信済み';
      // 送信済みのチェックを視覚的に無効化
      checks.forEach(cb => {{ cb.disabled = true; }});
    }}
  }} catch (e) {{
    showResult('通信エラーが発生しました', 'error');
    btn.disabled = false;
    btn.textContent = '深掘り開始';
  }}
}}

function showResult(msg, type) {{
  const el = document.getElementById('result-msg');
  el.textContent = msg;
  el.className = 'result-msg ' + type;
  el.style.display = 'block';
}}

// アニメーション背景（既存コードと同じパターン）
(function() {{
  const canvas = document.getElementById('bg-canvas');
  const ctx = canvas.getContext('2d');
  let w, h, lines = [], time = 0, scrollSpeed = 0, lastScroll = 0;
  const LINE_COUNT = 18;
  function initLines() {{
    lines = [];
    for (let i = 0; i < LINE_COUNT; i++) {{
      const pts = [];
      const numPts = 4 + Math.floor(Math.random() * 3);
      for (let j = 0; j < numPts; j++) {{
        pts.push({{ x: (j / (numPts - 1)) * w * 1.4 - w * 0.2, baseY: Math.random() * h }});
      }}
      lines.push({{ pts, opacity: 0.15 + Math.random() * 0.2, width: 0.8 + Math.random() * 1.2 }});
    }}
  }}
  function resize() {{
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    initLines();
  }}
  window.addEventListener('resize', resize);
  resize();
  const blobs = [
    {{ x: 0.7, y: 0.3, r: 0.45, color: [235, 136, 104] }},
    {{ x: 0.3, y: 0.7, r: 0.50, color: [52, 183, 223] }},
    {{ x: 0.5, y: 0.2, r: 0.35, color: [52, 183, 223] }},
    {{ x: 0.8, y: 0.8, r: 0.30, color: [235, 136, 104] }},
  ];
  window.addEventListener('scroll', function() {{
    const st = window.scrollY || document.documentElement.scrollTop;
    scrollSpeed = Math.min(Math.abs(st - lastScroll) * 0.002, 0.015);
    lastScroll = st;
  }}, {{ passive: true }});
  function draw() {{
    time += 0.003 + scrollSpeed;
    scrollSpeed *= 0.95;
    ctx.fillStyle = 'rgb(233,233,233)';
    ctx.fillRect(0, 0, w, h);
    for (let b = 0; b < blobs.length; b++) {{
      const bl = blobs[b];
      const bx = w * (bl.x + Math.sin(time * 0.4 + b * 2.1) * 0.08);
      const by = h * (bl.y + Math.cos(time * 0.3 + b * 1.7) * 0.06);
      const br = Math.max(w, h) * bl.r;
      const grd = ctx.createRadialGradient(bx, by, 0, bx, by, br);
      grd.addColorStop(0, 'rgba(' + bl.color[0] + ',' + bl.color[1] + ',' + bl.color[2] + ',0.06)');
      grd.addColorStop(0.6, 'rgba(' + bl.color[0] + ',' + bl.color[1] + ',' + bl.color[2] + ',0.02)');
      grd.addColorStop(1, 'rgba(' + bl.color[0] + ',' + bl.color[1] + ',' + bl.color[2] + ',0)');
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, w, h);
    }}
    for (let i = 0; i < lines.length; i++) {{
      const L = lines[i];
      const pts = L.pts;
      ctx.beginPath();
      const y0 = pts[0].baseY + Math.sin(time * 0.5 + i * 1.7) * 40;
      ctx.moveTo(pts[0].x, y0);
      for (let j = 1; j < pts.length - 1; j++) {{
        const yj = pts[j].baseY + Math.sin(time * (0.5 + j * 0.2) + i * 1.7) * 40;
        const yjn = pts[j + 1].baseY + Math.sin(time * (0.5 + (j + 1) * 0.2) + i * 1.7) * 40;
        const cx = (pts[j].x + pts[j + 1].x) / 2;
        const cy = (yj + yjn) / 2;
        ctx.quadraticCurveTo(pts[j].x, yj, cx, cy);
      }}
      const last = pts[pts.length - 1];
      const yLast = last.baseY + Math.sin(time * (0.5 + (pts.length - 1) * 0.2) + i * 1.7) * 40;
      ctx.lineTo(last.x, yLast);
      ctx.strokeStyle = 'rgba(255,255,255,' + L.opacity + ')';
      ctx.lineWidth = L.width;
      ctx.stroke();
    }}
    requestAnimationFrame(draw);
  }}
  draw();
}})();
</script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return str(filepath)
