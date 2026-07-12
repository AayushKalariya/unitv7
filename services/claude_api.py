import os
import datetime
from typing import Generator
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096


def build_system_prompt(
    calendar_context: str,
    user_name: str = "User",
    rag_context: str = "",
) -> str:
    now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    rag_block = f"\n\n{rag_context}\n" if rag_context else ""
    return f"""You are Orb, a personal AI assistant running as a desktop widget.
Current date and time: {now}
User name: {user_name}

{calendar_context}
{rag_block}
Be concise, helpful, and conversational. When relevant, proactively reference the user's calendar context.

You have a web_search tool. Use it whenever a question needs current info, facts you're unsure of, or anything after your knowledge cutoff."""


def stream_response(
    messages: list[dict],
    calendar_context: str,
    user_name: str = "User",
    rag_context: str = "",
) -> Generator[str, None, None]:
    import anthropic
    from services.web_search import WEB_SEARCH_TOOL, web_search

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system_prompt = build_system_prompt(calendar_context, user_name, rag_context)

    working_messages = list(messages)

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=working_messages,
            tools=[WEB_SEARCH_TOOL],
        ) as stream:
            for text in stream.text_stream:
                yield text
            final_message = stream.get_final_message()

        if final_message.stop_reason != "tool_use":
            break

        working_messages.append({"role": "assistant", "content": final_message.content})
        tool_results = []
        for block in final_message.content:
            if block.type == "tool_use" and block.name == "web_search":
                result = web_search(block.input.get("query", ""))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        working_messages.append({"role": "user", "content": tool_results})
