"""チェイスエンジン: 毎日のタスク追跡通知を生成"""

from datetime import datetime, timedelta
import anthropic
from app.config import Config
from app import task_manager
from app.cost_tracker import record_cost


# キャラ設定: ストイックなトレーナー
CHASE_PERSONA = """あなたはRIO専属のストイックなトレーナー。
- 無駄な言葉は使わない。短く、的確に指示する
- 「やるべきこと」と「やり方」を明確に伝える
- 感情に寄り添うより、行動を促す
- 「さあ始めよう」「まず手を動かせ」のような着手を促す言い回し
- 絵文字は使わない
- 敬語は使わない、タメ口で話す
- RIOと呼ぶ"""


async def generate_morning_chase() -> str:
    """朝のチェイスメッセージを生成"""
    tasks = task_manager.get_today_tasks()

    if not tasks:
        return "今日やるタスクはありません。のんびりしましょう。"

    tasks_text = _format_tasks_for_prompt(tasks)

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=CHASE_PERSONA,
        messages=[
            {
                "role": "user",
                "content": f"""以下のタスクリストから、今日の朝のチェイスメッセージを生成してください。

タスク一覧:
{tasks_text}

ルール:
- 200文字以内で簡潔に
- 最も優先度の高い1件を「今日のメニュー」として推す
- 具体的な所要時間の目安を入れる
- 5分以内に終わるものがあれば「ウォーミングアップ」として先に推す
- LINEメッセージとして読みやすいフォーマット"""
            }
        ],
    )

    record_cost("claude-haiku-4-5-20251001", message.usage.input_tokens, message.usage.output_tokens, "朝チェイス")

    return message.content[0].text.strip()


async def generate_chase_for_task(task: dict) -> str:
    """個別タスクのチェイスメッセージを生成"""
    days_since = _days_since_created(task)
    postpone_count = task.get("postpone_count", 0)
    deadline = task.get("deadline", "")
    is_overdue = deadline and deadline < datetime.now().strftime("%Y-%m-%d")

    # 状況に応じたトレーナーの指示
    if is_overdue:
        prompt_extra = "期限が過ぎている。「マジでヤバい、今日中にやれ」くらいの強い口調で。"
    elif postpone_count >= 3:
        prompt_extra = "3回以上先延ばしされている。「本当にやるのか、やめるのか決めろ」とストレートに聞く。"
    elif days_since >= 14:
        prompt_extra = "2週間以上放置されている。「これまだメニューに入れとく意味あるか?」と棚卸しを提案。"
    elif days_since >= 3 and task.get("chase_count", 0) >= 3:
        prompt_extra = "3日以上進んでいない。「何が引っかかってる?」とブロッカーを聞く。"
    else:
        prompt_extra = "シンプルに着手を促す。"

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=CHASE_PERSONA,
        messages=[
            {
                "role": "user",
                "content": f"""以下のタスクのチェイスメッセージを生成してください。

タスク: {task["title"]}
期限: {deadline or "なし"}
作成から{days_since}日経過
先延ばし回数: {postpone_count}回

{prompt_extra}

ルール:
- 100文字以内
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
