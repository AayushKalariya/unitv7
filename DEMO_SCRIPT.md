# Orb Assistant — Hackathon Demo Script

**Total run time: ~3 minutes.** Optimized for the *Presentation* rubric: convincing pitch, clear idea, live working demo.

---

## 0. Before you walk on stage (setup checklist)

Do all of this so nothing breaks live:

- [ ] `.env` filled: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- [ ] Google Calendar `token.json` present + at least **one fake event today** (e.g. "Demo Day pitch @ 2:00 PM") — makes the calendar moment land
- [ ] App already running (`python main.py`) — orb floating on screen. **Never boot cold on stage.**
- [ ] One PDF/doc ready to drag in (e.g. a resume, a paper, or the hackathon rules PDF)
- [ ] Mic tested — say "Hey Jarvis" once before judges arrive to confirm wake word fires
- [ ] Chat history cleared (New Chat) so the panel looks clean
- [ ] Backup plan: if voice fails, type instead. Have this script open on a second screen.

---

## 1. The Hook (0:00–0:20)

> "Every AI assistant lives in a browser tab you have to go find. Ours lives **on your screen, always** — one glowing orb, floating over everything you do. You talk to it, drop files on it, and it already knows your day. This is **Orb**."

*(Point at the floating orb. Let it shimmer for a beat.)*

---

## 2. The Problem (0:20–0:35)

> "Switching to ChatGPT means stopping what you're doing, opening a tab, re-explaining your context every time. The assistant has no idea what's on your calendar, can't see your documents, and forgets you the moment you close it. We fixed all three."

---

## 3. Live Demo — the core loop (0:35–2:30)

Run these **in order**. Each beat proves one feature. Say the line, do the action, let the result show.

### Beat 1 — Voice + the living orb (offline speech)
- **Say out loud:** "Hey Jarvis."
- Orb lights up / pulses (listening state — real GLSL shader reacting).
- **Ask:** "What's on my calendar today?"
- Orb answers using **real Google Calendar data**, streaming token-by-token.

> "That was fully hands-free. Wake word and speech-to-text run **locally on-device** with Whisper — no audio ever leaves this machine. And it already pulled my real calendar into the answer."

### Beat 2 — Agentic web search (live info)
- **Type or say:** "What's the weather right now where TechCrunch Disrupt is happening this week?" *(or any question needing fresh data)*

> "It doesn't hallucinate current events. Claude decides on its own to call a live web-search tool, reads the results, and answers. That's a real agent loop — tool call, tool result, final answer."

### Beat 3 — RAG / talk to your documents (the showstopper)
- **Drag a PDF onto the panel.**
- Status shows: `📎 Reading "…"` → `✓ Added (N chunks). Ask me anything about it.`
- **Ask something only answerable from that file**, e.g. "Summarize the three main points" or "What's this person's most recent job?"

> "I just dropped a document in. It got parsed, chunked, embedded, and stored in a vector database in seconds — and now I can ask questions about it and it cites the source. Each chat has its own private memory of what you've shown it."

### Beat 4 — Persistent memory (optional, if time)
- Open history → show past sessions.

> "Close it, reopen it — every conversation and every document is still here. It remembers you."

---

## 4. How it's built (0:30 — say while the last answer streams)

> "Under the hood: **Claude Sonnet 5** for reasoning, **Whisper** running locally for voice, **openWakeWord** for the wake word, **Tavily** for live search, **Supabase pgvector** for document memory, and a hand-written **OpenGL shader** for the orb. All wired into a native desktop widget — no browser, no tab, always one keyword away."

---

## 5. The Close (0:20)

> "Orb is the assistant that's actually *present* — it sees your day, reads your files, hears you across the room, and never makes you switch context. Thanks — we'd love your questions."

---

## Judge Q&A — likely questions + crisp answers

- **"Is the voice cloud-based?"** → No. Wake word (openWakeWord) and transcription (faster-whisper) run 100% locally. Privacy by default.
- **"What happens if a service is down?"** → Graceful degradation — RAG failing never breaks chat, calendar/search errors fall back silently. It's built to not crash mid-conversation.
- **"How is document data isolated?"** → Every chunk is scoped to a session ID in the vector store; one chat can't read another's files.
- **"Why a desktop widget instead of a web app?"** → Zero context-switch. It's always on top, wake-word triggered, and can see local files a browser tab can't.
- **"What would you add next?"** → Custom "Hey Orb" wake word, screen-awareness, and local action-taking (open apps, control files).

---

## One-liner for the intro slide / Devpost

> **Orb** — an always-on desktop AI orb you talk to out loud. It knows your calendar, reads any file you drop on it, searches the live web, and remembers every conversation — all without opening a single browser tab.
