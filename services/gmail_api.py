import base64
from email.mime.text import MIMEText

from services.google_auth import get_credentials

CREATE_DRAFT_TOOL = {
    "name": "create_draft",
    "description": (
        "Create a draft email in the user's Gmail account. The draft is saved but "
        "NOT sent — the user reviews and sends it manually in Gmail. Use this when the "
        "user wants to prepare an email, e.g. a networking message from a saved template. "
        "Fill any {placeholders} from a template before calling. Always confirm the "
        "recipient, subject, and body with the user if any detail is unclear."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string", "description": "Email subject line."},
            "body": {"type": "string", "description": "Full email body (plain text)."},
        },
        "required": ["to", "subject", "body"],
    },
}


def create_draft(to: str, subject: str, body: str) -> str:
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        if not creds:
            return "Gmail is not configured (missing credentials.json)."

        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        draft_id = draft.get("id", "unknown")
        return (
            f"Draft created successfully (id: {draft_id}). "
            f"To: {to} | Subject: {subject}. It's saved in Gmail Drafts, not sent."
        )
    except Exception as e:
        return f"Failed to create draft: {e}"
