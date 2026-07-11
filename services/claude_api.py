import os
import datetime
from typing import Generator
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096


def build_system_prompt(calendar_context: str, user_name: str = "User") -> str:
    now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    return f"""You are Orb, a personal AI assistant running as a desktop widget.
Current date and time: {now}
User name: {user_name}

{calendar_context}

Be concise, helpful, and conversational. When relevant, proactively reference the user's calendar context."""


def stream_response(
    messages: list[dict],
    calendar_context: str,
    user_name: str = "User",
) -> Generator[str, None, None]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system_prompt = build_system_prompt(calendar_context, user_name)

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
