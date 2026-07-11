import json
import os

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "chat_history.json")


def load_history() -> list:
    path = os.path.abspath(HISTORY_FILE)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_history(messages: list) -> None:
    path = os.path.abspath(HISTORY_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def clear_history() -> None:
    path = os.path.abspath(HISTORY_FILE)
    if os.path.exists(path):
        os.remove(path)
