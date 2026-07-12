import os

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "token.json")

# All Google scopes the app needs, requested together so a single token.json
# covers every service. Adding a scope here means the next auth run will prompt
# for consent again (old tokens won't carry the new scope).
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_credentials():
    """Return valid Google OAuth credentials, or None if unavailable.

    Runs the local-server consent flow on first use and refreshes expired
    tokens automatically. Shared by all Google service wrappers.
    """
    credentials_path = os.path.abspath(CREDENTIALS_FILE)
    token_path = os.path.abspath(TOKEN_FILE)

    if not os.path.exists(credentials_path):
        return None

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

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

    return creds
