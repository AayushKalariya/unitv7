# Orb Assistant

> An always-on desktop AI orb you talk to out loud. It knows your calendar, reads any file you drop on it, searches the live web, drafts your emails, and remembers every conversation — all without opening a single browser tab.

Orb lives on your screen as a small floating widget instead of another browser tab. Click it to chat, or say the wake word to talk hands-free. It's backed by Claude with tool access to your calendar, the live web, your local documents, and your Gmail drafts.

## Features

- **Floating desktop orb** — always-on-top widget (OpenGL shader animation) that expands into a chat panel on click.
- **Voice, fully local** — wake word detection + offline speech-to-text. No audio leaves the machine.
- **Google Calendar awareness** — pulls upcoming events into every conversation automatically.
- **Live web search** — Claude decides on its own when to search for current information via Tavily.
- **Gmail draft automation** — save a reusable email template with `{placeholders}`, then ask Orb to draft it to a contact. It fills the template and saves a real Gmail draft — never sends automatically, always reviewable.
- **RAG over your documents** — drag a PDF/doc onto the panel; it's parsed, chunked, embedded, and stored so you can ask questions about it.
- **Persistent multi-session memory** — every chat and its document context survives restarts, switchable like tabs.

## Tech Stack

**Language:** Python, SQL

**Core**
- [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) — Claude API client, streaming + tool-use agent loop
- `PyQt6` — desktop UI framework
- `PyOpenGL` / `PyOpenGL_accelerate` — orb shader rendering
- `python-dotenv` — environment config

**Voice**
- `openwakeword` — local wake word detection
- `pvrecorder` — microphone capture
- `faster-whisper` — local speech-to-text
- `numpy` — audio processing

**Google integration**
- `google-api-python-client` — Calendar + Gmail APIs
- `google-auth-oauthlib` — OAuth flow

**Search**
- `tavily-python` — live web search tool

**RAG (document memory)**
- `docling` — document parsing
- `chonkie` — text chunking
- `fastembed` — local embeddings
- `supabase` — pgvector storage, session-scoped

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Create `.env` with:
   ```
   ANTHROPIC_API_KEY=
   TAVILY_API_KEY=
   SUPABASE_URL=
   SUPABASE_KEY=
   ```
3. Add Google OAuth `credentials.json` (Cloud Console → enable **Calendar API** and **Gmail API** on the same project).
4. Run:
   ```
   python main.py
   ```
   First run opens a browser consent screen for Google (Calendar read + Gmail draft-compose scopes).

## Architecture

- `main.py` — app entrypoint, tray icon, orb/panel wiring
- `ui/` — orb widget (OpenGL) and chat panel (PyQt6)
- `services/` — Claude agent loop, Google auth, calendar, Gmail drafts, email templates, web search, voice, RAG
- `storage/` — local JSON persistence: chat sessions, email templates
- `sql/schema.sql` — Supabase/pgvector schema for RAG document chunks

## Inspiration

Desktop assistants always felt buried — another browser tab, another app window competing for space. We wanted something that lived *on* the desktop itself: a small persistent orb, always one click away, that felt more like a companion than a chatbot. The idea crystallized around a real annoyance: repetitive networking emails. Writing the same intro message to ten different contacts, swapping in a name and company each time, is exactly the kind of task an assistant should just handle.

## How we built it

Started with the shell: a system tray + always-on-top orb window using PyQt6, click handlers toggling a slide-out chat panel. Then wired Claude's streaming API for token-by-token responses so the UI feels alive instead of waiting on a spinner.

Google integrations (Calendar, Gmail) share one OAuth flow and one `token.json`, requesting combined scopes up front so we don't juggle multiple credential files. Tool-calling is handled through a single dispatcher in the Claude service layer — each capability (search, draft, save template) is defined as a schema + handler function, and Claude decides when to invoke them mid-conversation, looping until it produces a final text response.

Templates are stored as simple named JSON records with subject/body placeholders. Every turn, we inject the user's saved templates into the system prompt so Claude can reference them by name without a separate lookup tool call.

## What we learned

- Tool-use loops need careful state handling — appending assistant tool-call turns and tool-result turns back into the message list correctly is easy to get subtly wrong and silently breaks the conversation.
- Scoping OAuth incrementally is painful: adding a new Google API scope invalidates the old token silently rather than loudly.
- Keeping side effects (like sending real email) *reversible* changes the whole design — drafting-only was the right call, since it lets the assistant act confidently without needing to be perfectly right every time.

## Challenges we ran into

- **OAuth scope drift** — the original token only covered Calendar; adding Gmail required regenerating it, and Google doesn't make that failure obvious.
- **Streaming + tool calls together** — chaining live token streaming with a multi-step tool loop meant handling partial state carefully so the UI doesn't show broken or duplicated output.
- **Balancing autonomy with safety** — letting the assistant write emails on your behalf is powerful but risky; the guardrail (drafts only, confirm ambiguous details) took iteration to get right in the system prompt.
