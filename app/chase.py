"""チェイスエンジン: 毎日のタスク追跡通知を生成"""

from datetime import datetime, timedelta
import anthropic
from app.config import Config
from app import task_manager
from app.cost_tracker import record_cost


# トーンのバリエーション（日替わり）
CHASE_TONES = [
    "フレンドリーな先輩風（気軽だけど的確）",
    "熱血コーチ風（やる気を出させる）",
    "クールな執事風（丁寧だけど容赦ない）",
    "ゲーム実況風（タスク完了をミッションクリアとして盛り上げる）",
    "親しい友達風（カジュアルに背中を押す）",
    "軍師風（戦略的にタスクを攻略する提案）",
    "応援団長風（全力で応援する）",
]


def get_today_tone() -> str:
    """日替わりでトーンを変える"""
    day_of_year = datetime.now().timetuple().tm_yday
    return CHASE_TONES[day_of_year % len(CHASE_TONES)]


async def generate_morning_chase() -> str:
    """朝のチェイスメッセージを生成"""
    tasks = task_manager.get_today_tasks()

    if not tasks:
        return "今日やるタスクはありません。のんびりしましょう。"

    tone = get_today_tone()
    tasks_text = _format_tasks_for_prompt(tasks)

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""以下のタスクリストから、今日のチェイスメッセージを生成してください。

トーン: {tone}

タスク一覧:
{tasks_text}

ルール:
- 200文字以内で簡潔に
- 最も優先度の高い1件を「今日はこれだけはやろう」として推す
- 5分以内に終わるものがあれば先に推す
- 絵文字は使わない
- LINEメッセージとして読みやすいフォーマット"""
            }
        ],
    )

    record_cost("claude-haiku-4-5-20251001", message.usage.input_tokens, message.usage.output_tokens, "朝チェイス")

    return message.content[0].text.strip()


async def generate_chase_for_task(task: dict) -> str:
    """個別タスクのチェイスメッセージを生成"""
    tone = get_today_tone()
    days_since = _days_since_created(task)
    postpone_count = task.get("postpone_count", 0)

    # 3回連続「あとでやる」の場合
    if postpone_count >= 3:
        prompt_extra = "このタスクは3回以上先延ばしにされています。「本当にやる？やめる？」と確認してください。"
    # 3日放置の場合
    elif days_since >= 3 and task.get("chase_count", 0) >= 3:
        prompt_extra = "このタスクは3日以上放置されています。「何がブロッカー？」と質問してください。"
    # 2週間放置の場合
    elif days_since >= 14:
        prompt_extra = "このタスクは2週間以上放置されています。「これまだいる？」と棚卸し提案をしてください。"
    else:
        prompt_extra = "前向きにやる気を出させるメッセージにしてください。"

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": f"""以下のタスクのチェイスメッセージを生成してください。

トーン: {tone}
タスク: {task["title"]}
期限: {task.get("deadline", "なし")}
作成から{days_since}日経過
先延ばし回数: {postpone_count}回

{prompt_extra}

ルール:
- 100文字以内
- 絵文字は使わない
- LINEメッセージとして読みやすく"""
            }
        ],
    )

    record_cost("claude-haiku-4-5-20251001", message.usage.input_tokens, message.usage.output_tokens, "個別チェイス")

    return message.content[0].text.strip()


def get_tasks_needing_chase() -> list[dict]:
    """チェイスが必要なタスクを取得"""
    tasks = task_manager.get_active_tasks()
    now = datetime.now()
    result = []

    for task in tasks:
        deadline = task.get("deadline", "")
        last_chased = task.get("last_chased_at", "")

        # 最後のチェイスからの経過時間
        if last_chased:
            last_dt = datetime.fromisoformat(last_chased)
            hours_since_chase = (now - last_dt).total_seconds() / 3600
        else:
            hours_since_chase = 999

        # チェイス頻度の判定
        if deadline:
            days_until = (datetime.strptime(deadline, "%Y-%m-%d") - now).days
            if days_until <= 0:
                # 当日: 朝昼夕の3回（8時間ごと）
                if hours_since_chase >= 5:
                    result.append(task)
            elif days_until <= 3:
                # 3日以内: 朝夕の2回（12時間ごと）
                if hours_since_chase >= 10:
                    result.append(task)
            else:
                # 3日以上先: 毎日1回（24時間ごと）
                if hours_since_chase >= 20:
                    result.append(task)
        else:
            # 期限なし: 毎日1回
            if hours_since_chase >= 20:
                result.append(task)

    return result


def _format_tasks_for_prompt(tasks: list[dict]) -> str:
    lines = []
    for t in tasks:
        deadline_str = f"期限: {t['deadline']}" if t.get("deadline") else "期限なし"
        lines.append(f"- [{t['id']}] {t['title']} ({deadline_str})")
    return "\n".join(lines)


def _days_since_created(task: dict) -> int:
    created = datetime.fromisoformat(task["created_at"])
    return (datetime.now() - created).days
