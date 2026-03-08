"""HTML生成: 調査結果をHTMLファイルに変換"""

import secrets
from datetime import datetime
from pathlib import Path

import os

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "reports"


def generate_report_html(task: dict, research: dict, raw_input: str = "") -> str:
    """タスク情報と調査結果からHTMLを生成し、ファイルパスを返す"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    random_id = secrets.token_urlsafe(8)
    filename = f"rpt-{random_id}.html"
    filepath = OUTPUT_DIR / filename

    # タグ生成
    task_type_label = "行動が必要" if task.get("task_type") != "research" else "調べもの"
    task_type_class = "tag-action" if task.get("task_type") != "research" else "tag-research"
    deadline_tag = f'<span class="task-tag tag-deadline">期限 {task["deadline"]}</span>' if task.get("deadline") else ""

    # チェックリスト生成
    checklist_html = ""
    for item in research.get("checklist", []):
        dep_html = ""
        if item.get("depends_on"):
            dep_html = f'<div class="check-dep">-- {item["depends_on"]}の後</div>'
        checklist_html += f"""
  <div class="check-item">
    <div class="check-box"></div>
    <div>
      <div class="check-text">{item["item"]}</div>
      {dep_html}
    </div>
  </div>"""

    # 面倒ポイント生成
    hassle_html = ""
    for hp in research.get("hassle_points", []):
        hassle_html += f"""
  <div class="hassle-item">
    <div class="hassle-q">{hp["point"]}</div>
    <div class="hassle-a">{hp["solution"]}</div>
  </div>"""

    # エビデンス生成
    evidence_html = ""
    for ev in research.get("evidence", []):
        evidence_html += f"<li>{ev}</li>"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>{task["title"]} - タスク調査結果</title>
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
  --warn: #f59e0b;
  --ng: #ef4444;
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
  padding: 24px 16px;
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
  max-width: 720px;
  margin: 0 auto;
}}
.task-header {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh2);
  padding: 24px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.task-header::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--coral), var(--sky));
}}
.task-meta {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}}
.task-tag {{
  font-size: 10px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 99px;
  letter-spacing: .03em;
}}
.tag-action {{ background: var(--coral-light); color: var(--coral); }}
.tag-research {{ background: var(--sky-light); color: var(--sky); }}
.tag-deadline {{ background: var(--sky-light); color: var(--sky); }}
.tag-time {{ background: rgba(34,197,94,.08); color: var(--ok); }}
.task-title {{
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -.02em;
  line-height: 1.3;
  margin-bottom: 4px;
}}
.task-date {{
  font-size: 11px;
  color: var(--tx3);
  font-family: 'DM Sans', sans-serif;
}}
.next-action {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh2);
  padding: 20px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.next-action::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--coral);
}}
.next-label {{
  font-size: 9px;
  font-weight: 700;
  color: var(--coral);
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.next-text {{
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}}
.next-sub {{
  font-size: 12px;
  color: var(--tx2);
  margin-top: 6px;
}}
.checklist-card {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  padding: 20px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.checklist-card::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--sky);
}}
.section-label {{
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.section-dot {{
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.check-item {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0,0,0,.03);
}}
.check-item:last-child {{ border-bottom: none; }}
.check-box {{
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid var(--bd);
  background: #fff;
  flex-shrink: 0;
  margin-top: 1px;
}}
.check-text {{
  font-size: 13px;
  font-weight: 500;
  line-height: 1.5;
}}
.check-dep {{
  font-size: 10px;
  color: var(--sky);
  font-weight: 500;
  margin-top: 2px;
}}
.info-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}}
@media (max-width: 520px) {{
  .info-grid {{ grid-template-columns: 1fr; }}
}}
.info-card {{
  background: var(--shimmer);
  border-radius: 2px 10px 10px 2px;
  box-shadow: var(--sh);
  padding: 16px 20px;
  position: relative;
  overflow: hidden;
}}
.info-card::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
}}
.info-card.time::before {{ background: var(--sky); }}
.info-card.cost::before {{ background: var(--ok); }}
.info-label {{
  font-size: 9px;
  font-weight: 600;
  color: var(--tx3);
  letter-spacing: .06em;
  text-transform: uppercase;
  margin-bottom: 6px;
}}
.info-value {{
  font-family: 'DM Sans', sans-serif;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}}
.risk-banner {{
  background: rgba(239,68,68,.04);
  border-radius: 2px 10px 10px 2px;
  padding: 16px 20px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.risk-banner::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--ng);
}}
.risk-label {{
  font-size: 10px;
  font-weight: 700;
  color: var(--ng);
  margin-bottom: 6px;
}}
.risk-text {{
  font-size: 13px;
  font-weight: 500;
  line-height: 1.6;
}}
.hassle-card {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  padding: 20px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
}}
.hassle-card::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: var(--warn);
}}
.hassle-item {{
  padding: 10px 0;
  border-bottom: 1px solid rgba(0,0,0,.03);
}}
.hassle-item:last-child {{ border-bottom: none; }}
.hassle-q {{
  font-size: 12px;
  font-weight: 600;
  color: var(--tx);
  margin-bottom: 4px;
}}
.hassle-a {{
  font-size: 12px;
  color: var(--tx2);
  line-height: 1.6;
}}
.detail-section {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  overflow: hidden;
  margin-bottom: 16px;
}}
.detail-toggle {{
  width: 100%;
  padding: 14px 28px;
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  color: var(--tx);
}}
.detail-toggle .arrow {{
  font-size: 10px;
  color: var(--tx3);
  transition: transform .2s;
}}
.detail-content {{
  display: none;
  padding: 0 28px 18px;
  font-size: 12px;
  color: var(--tx2);
  line-height: 1.7;
}}
.detail-content.open {{ display: block; }}
.detail-content li {{ margin-bottom: 4px; }}
.schedule-note {{
  background: var(--shimmer);
  border-radius: 2px 14px 14px 2px;
  box-shadow: var(--sh);
  padding: 16px 28px;
  position: relative;
  overflow: hidden;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--tx2);
  line-height: 1.6;
}}
.schedule-note::before {{
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--coral), var(--sky));
}}
.task-footer {{
  text-align: center;
  padding: 20px 0 10px;
  font-size: 10px;
  color: var(--tx3);
}}
</style>
</head>
<body>
<canvas id="bg-canvas"></canvas>
<div id="bg-grain"></div>
<div class="content-wrap">

<div class="task-header">
  <div class="task-meta">
    <span class="task-tag {task_type_class}">{task_type_label}</span>
    {deadline_tag}
    <span class="task-tag tag-time">所要 {research.get("time_estimate", "不明")}</span>
  </div>
  <h1 class="task-title">{task["title"]}</h1>
  <div class="task-date">調査日: {today}</div>
</div>

{f"""<div class="checklist-card">
  <div class="section-label">
    <span class="section-dot" style="background: var(--tx3)"></span>
    RIOの原文
  </div>
  <div style="font-size: 13px; line-height: 1.8; color: var(--tx2); white-space: pre-line; padding: 4px 0;">{raw_input}</div>
</div>""" if raw_input else ""}

<div class="next-action">
  <div class="next-label">Next Action</div>
  <div class="next-text">{research.get("next_action", "")}</div>
  <div class="next-sub">{research.get("schedule_suggestion", "")}</div>
</div>

<div class="checklist-card">
  <div class="section-label">
    <span class="section-dot" style="background: var(--sky)"></span>
    やることリスト
  </div>
  {checklist_html}
</div>

<div class="info-grid">
  <div class="info-card time">
    <div class="info-label">所要時間</div>
    <div class="info-value">{research.get("time_estimate", "不明")}</div>
  </div>
  <div class="info-card cost">
    <div class="info-label">費用</div>
    <div class="info-value">{research.get("cost_estimate", "不明")}</div>
  </div>
</div>

<div class="risk-banner">
  <div class="risk-label">やらなかった場合</div>
  <div class="risk-text">{research.get("risk", "")}</div>
</div>

{f'''<div class="hassle-card">
  <div class="section-label">
    <span class="section-dot" style="background: var(--warn)"></span>
    面倒ポイントの解消
  </div>
  {hassle_html}
</div>''' if hassle_html else ""}

{f'''<div class="detail-section">
  <button class="detail-toggle" onclick="toggleDetail(this)">
    <span>詳細情報</span>
    <span class="arrow">&#9660;</span>
  </button>
  <div class="detail-content">
    <p>{research.get("details", "")}</p>
    {f"<ul>{evidence_html}</ul>" if evidence_html else ""}
  </div>
</div>''' if research.get("details") else ""}

{f'''<div class="schedule-note">
  <div class="section-label">
    <span class="section-dot" style="background: var(--coral)"></span>
    おすすめタイミング
  </div>
  <p>{research.get("schedule_suggestion", "")}</p>
</div>''' if research.get("schedule_suggestion") else ""}

<div class="task-footer">
  Task Chase System -- Generated {today}
</div>

</div>

<script>
function toggleDetail(btn) {{
  const content = btn.nextElementSibling;
  const arrow = btn.querySelector('.arrow');
  content.classList.toggle('open');
  arrow.style.transform = content.classList.contains('open') ? 'rotate(180deg)' : '';
}}

(function() {{
  const canvas = document.getElementById('bg-canvas');
  const ctx = canvas.getContext('2d');
  let w, h;
  let lines = [];
  const LINE_COUNT = 18;
  let time = 0;
  let scrollSpeed = 0;
  let lastScroll = 0;
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
