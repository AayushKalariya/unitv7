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
    template_context: str = "",
) -> str:
    now = datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    rag_block = f"\n\n{rag_context}\n" if rag_context else ""
    template_block = f"\n\n{template_context}\n" if template_context else ""
    return f"""You are Orb, a personal AI assistant running as a desktop widget.
Current date and time: {now}
User name: {user_name}

{calendar_context}
{template_block}{rag_block}
Be concise, helpful, and conversational. When relevant, proactively reference the user's calendar context.

You have a web_search tool. Use it whenever a question needs current info, facts you're unsure of, or anything after your knowledge cutoff.

Email tools: You can save reusable email templates (save_template), delete them (delete_template), and create Gmail drafts (create_draft). When a user wants to email someone from a template, load the matching saved template, fill in every {{placeholder}} using the details they gave (recipient name, company, etc.), then call create_draft with the recipient address, subject, and filled body. Drafts are never sent automatically — they are saved to Gmail Drafts for the user to review and send. If any detail (recipient, subject, or which template) is unclear, ask before drafting."""


def _dispatch_tool(name: str, args: dict) -> str:
    from services.web_search import web_search
    from services.gmail_api import create_draft
    from services.template_tools import handle_save_template, handle_delete_template

    if name == "web_search":
        return web_search(args.get("query", ""))
    if name == "create_draft":
        return create_draft(args.get("to", ""), args.get("subject", ""), args.get("body", ""))
    if name == "save_template":
        return handle_save_template(args.get("name", ""), args.get("subject", ""), args.get("body", ""))
    if name == "delete_template":
        return handle_delete_template(args.get("name", ""))
    return f"Unknown tool: {name}"


def stream_response(
    messages: list[dict],
    calendar_context: str,
    user_name: str = "User",
    rag_context: str = "",
    template_context: str = "",
) -> Generator[str, None, None]:
    import anthropic
    from services.web_search import WEB_SEARCH_TOOL
    from services.gmail_api import CREATE_DRAFT_TOOL
    from services.template_tools import SAVE_TEMPLATE_TOOL, DELETE_TEMPLATE_TOOL

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    system_prompt = build_system_prompt(
        calendar_context, user_name, rag_context, template_context
    )
    tools = [WEB_SEARCH_TOOL, CREATE_DRAFT_TOOL, SAVE_TEMPLATE_TOOL, DELETE_TEMPLATE_TOOL]

    working_messages = list(messages)

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=working_messages,
            tools=tools,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final_message = stream.get_final_message()

        if final_message.stop_reason != "tool_use":
            break

        working_messages.append({"role": "assistant", "content": final_message.content})
        tool_results = []
        for block in final_message.content:
            if block.type == "tool_use":
                result = _dispatch_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        working_messages.append({"role": "user", "content": tool_results})
