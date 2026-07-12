import json
import os
from datetime import datetime

TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "..", "email_templates.json")


def _path() -> str:
    return os.path.abspath(TEMPLATES_FILE)


def _now() -> str:
    return datetime.now().isoformat()


def load_templates() -> dict:
    """Return {name: {"name", "subject", "body", "updated_at"}}."""
    path = _path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    return data if isinstance(data, dict) else {}


def save_templates(templates: dict) -> None:
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def save_template(name: str, subject: str, body: str) -> dict:
    templates = load_templates()
    templates[name] = {
        "name": name,
        "subject": subject,
        "body": body,
        "updated_at": _now(),
    }
    save_templates(templates)
    return templates[name]


def get_template(name: str) -> dict | None:
    return load_templates().get(name)


def delete_template(name: str) -> bool:
    templates = load_templates()
    if name in templates:
        del templates[name]
        save_templates(templates)
        return True
    return False


def list_templates() -> list[dict]:
    templates = load_templates()
    return sorted(templates.values(), key=lambda t: t.get("name", "").lower())


def format_templates_for_prompt(templates: list[dict]) -> str:
    if not templates:
        return "No saved email templates yet."
    lines = ["Saved email templates (use {placeholders} to fill in per recipient):"]
    for t in templates:
        body = t.get("body", "")
        preview = body if len(body) <= 300 else body[:300] + "…"
        lines.append(
            f'  - Name: "{t.get("name", "")}"\n'
            f'    Subject: {t.get("subject", "")}\n'
            f'    Body: {preview}'
        )
    return "\n".join(lines)
