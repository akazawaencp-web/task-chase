"""タスク管理: タスクの登録・取得・更新・完了処理"""

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/task-chase-data"))
TASKS_FILE = DATA_DIR / "tasks.json"


def _load_tasks() -> list[dict]:
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tasks(tasks: list[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def _next_id(tasks: list[dict]) -> int:
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1


def add_task(title: str, description: str = "", deadline: str = "", raw_input: str = "") -> dict:
    """タスクを新規登録"""
    tasks = _load_tasks()
    task = {
        "id": _next_id(tasks),
        "title": title,
        "description": description,
        "deadline": deadline,
        "raw_input": raw_input,
        "status": "active",
        "dashboard_status": "unconfirmed",
        "genre": "",
        "task_type": "",
        "html_url": "",
        "calendar_event_id": "",
        "created_at": datetime.now().isoformat(),
        "completed_at": "",
        "is_working": False,
        "chase_count": 0,
        "postpone_count": 0,
        "last_chased_at": "",
        "hidden": False,
    }
    tasks.append(task)
    _save_tasks(tasks)
    return task


def get_task(task_id: int) -> dict | None:
    """IDでタスクを取得"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            return t
    return None


def get_active_tasks() -> list[dict]:
    """未完了のタスクを取得"""
    tasks = _load_tasks()
    return [t for t in tasks if t["status"] == "active"]


def get_all_tasks() -> list[dict]:
    """全タスクを取得（完了含む）"""
    return _load_tasks()


def get_today_tasks() -> list[dict]:
    """今日やるべきタスクを完了しやすい順で取得"""
    active = get_active_tasks()
    today = datetime.now().strftime("%Y-%m-%d")

    def sort_key(t):
        # 期限が今日のものを優先、次に期限が近いもの
        if t["deadline"] == today:
            return (0, t["deadline"])
        elif t["deadline"] and t["deadline"] < today:
            return (-1, t["deadline"])  # 期限切れを最優先
        elif t["deadline"]:
            return (1, t["deadline"])
        else:
            return (2, "9999-99-99")  # 期限なしは後ろ

    return sorted(active, key=sort_key)


def complete_task(task_id: int) -> dict | None:
    """タスクを完了にする"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["dashboard_status"] = "done"
            t["completed_at"] = datetime.now().isoformat()
            _save_tasks(tasks)
            return t
    return None


def postpone_task(task_id: int) -> dict | None:
    """タスクを『あとでやる』にする（翌日リスケ）"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["postpone_count"] += 1
            _save_tasks(tasks)
            return t
    return None


def update_task(task_id: int, updates: dict) -> dict | None:
    """タスクを更新する"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t.update(updates)
            _save_tasks(tasks)
            return t
    return None


def record_chase(task_id: int):
    """チェイス記録を更新"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["chase_count"] += 1
            t["last_chased_at"] = datetime.now().isoformat()
            _save_tasks(tasks)
            return t
    return None
