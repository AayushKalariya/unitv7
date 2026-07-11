import os
import datetime

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_upcoming_events(max_results: int = 10) -> list[dict]:
    credentials_path = os.path.abspath(CREDENTIALS_FILE)
    token_path = os.path.abspath(TOKEN_FILE)

    if not os.path.exists(credentials_path):
        return []

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.utcnow().isoformat() + "Z"
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])

    except Exception as e:
        print(f"[Calendar] Error: {e}")
        return []


def format_events_for_prompt(events: list[dict]) -> str:
    if not events:
        return "No upcoming calendar events."

    lines = ["Upcoming Google Calendar events:"]
    for event in events:
        start = event.get("start", {})
        dt = start.get("dateTime", start.get("date", "Unknown time"))
        summary = event.get("summary", "No title")
        location = event.get("location", "")
        loc_str = f" @ {location}" if location else ""
        lines.append(f"  - {summary}{loc_str} [{dt}]")
    return "\n".join(lines)
