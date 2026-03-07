"""費用トラッカー: API呼び出しごとのコストを記録"""

import json
import os
from datetime import datetime
from pathlib import Path

COST_FILE = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data")) / "costs.json"

# 料金表（1Mトークンあたりの円換算、1USD=150円想定）
PRICING = {
    "claude-sonnet-4-20250514": {"input": 0.45, "output": 2.25},  # $3/$15 per 1M
    "claude-haiku-4-5-20251001": {"input": 0.12, "output": 0.60},  # $0.8/$4 per 1M
}


def _load_costs() -> list[dict]:
    if not COST_FILE.exists():
        return []
    with open(COST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_costs(costs: list[dict]):
    COST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_FILE, "w", encoding="utf-8") as f:
        json.dump(costs, f, ensure_ascii=False, indent=2)


def record_cost(model: str, input_tokens: int, output_tokens: int, purpose: str):
    """API呼び出しのコストを記録"""
    pricing = PRICING.get(model, {"input": 0.45, "output": 2.25})
    cost_yen = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    costs = _load_costs()
    costs.append({
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_yen": round(cost_yen, 2),
        "purpose": purpose,
    })
    _save_costs(costs)


def get_monthly_summary() -> dict:
    """今月のコストサマリーを返す"""
    costs = _load_costs()
    now = datetime.now()
    month_prefix = now.strftime("%Y-%m")

    monthly = [c for c in costs if c["timestamp"].startswith(month_prefix)]

    total_yen = sum(c["cost_yen"] for c in monthly)
    by_purpose = {}
    for c in monthly:
        p = c["purpose"]
        by_purpose[p] = by_purpose.get(p, 0) + c["cost_yen"]

    return {
        "month": month_prefix,
        "total_yen": round(total_yen, 2),
        "call_count": len(monthly),
        "by_purpose": {k: round(v, 2) for k, v in by_purpose.items()},
    }


def format_monthly_report() -> str:
    """月次レポートのLINEメッセージ"""
    summary = get_monthly_summary()

    lines = [f"-- {summary['month']} API費用レポート --\n"]
    lines.append(f"合計: {summary['total_yen']}円")
    lines.append(f"API呼び出し: {summary['call_count']}回\n")

    if summary["by_purpose"]:
        lines.append("内訳:")
        for purpose, cost in sorted(summary["by_purpose"].items(), key=lambda x: -x[1]):
            lines.append(f"  {purpose}: {cost}円")

    lines.append(f"\n月額上限: 3,000円")
    return "\n".join(lines)
