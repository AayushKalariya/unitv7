import datetime

from services.google_auth import get_credentials


def get_upcoming_events(max_results: int = 10) -> list[dict]:
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        if not creds:
            return []

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
