import json
import os
import uuid
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "chat_history.json")


def _path() -> str:
    return os.path.abspath(HISTORY_FILE)


def _now() -> str:
    return datetime.now().isoformat()


def _empty_store() -> dict:
    return {"sessions": {}, "order": [], "active": None}


def _make_session(title: str = "New Chat") -> dict:
    return {
        "id": uuid.uuid4().hex,
        "title": title,
        "created_at": _now(),
        "updated_at": _now(),
        "messages": [],
    }


def _title_from_messages(messages: list) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            content = content.strip().replace("\n", " ")
            return content[:40] + ("…" if len(content) > 40 else "")
    return "New Chat"


def load_store() -> dict:
    path = _path()
    if not os.path.exists(path):
        store = _empty_store()
        session = _make_session()
        store["sessions"][session["id"]] = session
        store["order"] = [session["id"]]
        store["active"] = session["id"]
        return store

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = None

    if isinstance(data, list):
        # Legacy flat-history format: wrap it into a single session.
        store = _empty_store()
        session = _make_session(_title_from_messages(data))
        session["messages"] = data
        store["sessions"][session["id"]] = session
        store["order"] = [session["id"]]
        store["active"] = session["id"]
        return store

    if isinstance(data, dict) and "sessions" in data:
        if not data.get("order") or not data.get("active"):
            data.setdefault("sessions", {})
            data["order"] = list(data["sessions"].keys())
            data["active"] = data["order"][0] if data["order"] else None
        if not data["sessions"]:
            session = _make_session()
            data["sessions"][session["id"]] = session
            data["order"] = [session["id"]]
            data["active"] = session["id"]
        return data

    store = _empty_store()
    session = _make_session()
    store["sessions"][session["id"]] = session
    store["order"] = [session["id"]]
    store["active"] = session["id"]
    return store


def save_store(store: dict) -> None:
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def create_session(store: dict) -> dict:
    session = _make_session()
    store["sessions"][session["id"]] = session
    store["order"].insert(0, session["id"])
    store["active"] = session["id"]
    return session


def set_active_session(store: dict, session_id: str) -> None:
    if session_id in store["sessions"]:
        store["active"] = session_id


def get_active_session(store: dict) -> dict:
    return store["sessions"][store["active"]]


def update_active_messages(store: dict, messages: list) -> None:
    session = get_active_session(store)
    session["messages"] = messages
    session["updated_at"] = _now()
    if session["title"] == "New Chat":
        session["title"] = _title_from_messages(messages)


def clear_active_messages(store: dict) -> None:
    session = get_active_session(store)
    session["messages"] = []
    session["title"] = "New Chat"
    session["updated_at"] = _now()


def delete_session(store: dict, session_id: str) -> None:
    if session_id not in store["sessions"]:
        return
    del store["sessions"][session_id]
    store["order"] = [sid for sid in store["order"] if sid != session_id]
    if store["active"] == session_id:
        if store["order"]:
            store["active"] = store["order"][0]
        else:
            session = create_session(store)
            store["active"] = session["id"]


def list_sessions(store: dict) -> list:
    sessions = [store["sessions"][sid] for sid in store["order"] if sid in store["sessions"]]
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return [
        {"id": s["id"], "title": s["title"] or "New Chat", "updated_at": s["updated_at"]}
        for s in sessions
    ]
