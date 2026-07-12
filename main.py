import sys
import os
import threading

from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import Qt, QSize, QObject, pyqtSignal

from ui.orb_widget import OrbWindow
from ui.chat_panel import ChatPanel
from services.claude_api import stream_response
from services.calendar_api import get_upcoming_events, format_events_for_prompt
from services.voice import VoiceAssistant, preload_whisper_model
from services.rag import ingest_file, retrieve, is_configured as rag_configured
from storage.history import (
    load_store, save_store, create_session, set_active_session,
    get_active_session, update_active_messages, clear_active_messages,
    delete_session, list_sessions,
)


class _VoiceSignals(QObject):
    wake = pyqtSignal()
    transcript = pyqtSignal(str)
    error = pyqtSignal(str)


class _IngestSignals(QObject):
    status = pyqtSignal(str)   # progress / result note


def make_tray_icon() -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill(QColor(100, 50, 200))
    return QIcon(pix)


class OrbAssistant:
    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        threading.Thread(target=preload_whisper_model, daemon=True).start()

        self._store = load_store()
        self._messages: list[dict] = get_active_session(self._store)["messages"]
        self._panel_visible = False

        self._orb = OrbWindow(
            on_left_click=self._toggle_panel,
            on_right_click=self._show_tray_menu,
        )

        self._panel = ChatPanel()
        self._panel.message_submitted.connect(self._on_message)
        self._panel.clear_history_requested = self._on_clear_history
        self._panel.new_chat_requested.connect(self._on_new_chat)
        self._panel.session_selected.connect(self._on_session_selected)
        self._panel.session_delete_requested.connect(self._on_session_deleted)
        self._panel.history_opened.connect(self._refresh_session_list)
        self._panel.file_attached.connect(self._on_file_attached)

        self._ingest_signals = _IngestSignals()
        self._ingest_signals.status.connect(self._panel.add_status_message)

        if self._messages:
            self._panel.load_history(self._messages)

        self._tray = QSystemTrayIcon(make_tray_icon(), self._app)
        self._tray.setToolTip("Orb Assistant")
        tray_menu = QMenu()
        tray_menu.addAction("Show/Hide", self._toggle_panel)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.show()

        self._orb.show()

        self._voice_signals = _VoiceSignals()
        self._voice_signals.wake.connect(self._on_voice_wake)
        self._voice_signals.transcript.connect(self._on_voice_transcript)
        self._voice_signals.error.connect(self._on_voice_error)
        self._voice = VoiceAssistant(
            on_wake=self._voice_signals.wake.emit,
            on_transcript=self._voice_signals.transcript.emit,
            on_error=self._voice_signals.error.emit,
        )
        self._voice.start()

    def _toggle_panel(self):
        if self._panel_visible:
            self._panel.hide()
            self._panel_visible = False
        else:
            screen = QApplication.primaryScreen().geometry()
            self._panel.reposition_near_orb(
                self._orb.pos(), self._orb.size(), screen
            )
            self._panel.show()
            self._panel_visible = True

    def _show_tray_menu(self, pos):
        if self._tray.contextMenu():
            self._tray.contextMenu().exec(pos)

    def _on_message(self, text: str):
        self._messages.append({"role": "user", "content": text})
        self._panel.add_user_message(text)
        self._panel.show_loading()
        threading.Thread(target=self._stream_reply, daemon=True).start()

    def _active_session_id(self) -> str:
        return self._store["active"]

    def _on_file_attached(self, path: str):
        if not rag_configured():
            self._panel.add_status_message(
                "⚠ File storage not configured — add SUPABASE_URL and SUPABASE_KEY to .env."
            )
            return
        name = os.path.basename(path)
        self._panel.add_status_message(f"📎 Reading “{name}”…")
        session_id = self._active_session_id()
        threading.Thread(
            target=self._ingest_file, args=(session_id, path), daemon=True
        ).start()

    def _ingest_file(self, session_id: str, path: str):
        name = os.path.basename(path)
        try:
            result = ingest_file(session_id, path)
            self._ingest_signals.status.emit(
                f"✓ Added “{result['filename']}” ({result['n_chunks']} chunks). "
                f"Ask me anything about it."
            )
        except Exception as e:
            self._ingest_signals.status.emit(f"✕ Couldn't add “{name}”: {e}")

    def _stream_reply(self):
        try:
            events = get_upcoming_events(max_results=10)
            calendar_ctx = format_events_for_prompt(events)

            rag_ctx = ""
            last_user = next(
                (m["content"] for m in reversed(self._messages)
                 if m["role"] == "user" and isinstance(m["content"], str)),
                "",
            )
            if last_user:
                rag_ctx = retrieve(last_user, self._active_session_id())

            full_text = ""
            first = True

            for token in stream_response(self._messages, calendar_ctx, rag_context=rag_ctx):
                if first:
                    self._panel.stream_start()
                    first = False
                full_text += token
                self._panel.stream_token(token)

            self._panel.stream_done()

            self._messages.append({"role": "assistant", "content": full_text})
            update_active_messages(self._store, self._messages)
            save_store(self._store)

        except Exception as e:
            self._panel.stream_error(str(e))
            if self._messages and self._messages[-1]["role"] == "user":
                self._messages.pop()

    def _on_voice_wake(self):
        self._orb.set_listening(True)
        if not self._panel_visible:
            self._toggle_panel()

    def _on_voice_transcript(self, text: str):
        self._orb.set_listening(False)
        self._on_message(text)

    def _on_voice_error(self, msg: str):
        self._orb.set_listening(False)
        print(f"[voice] {msg}")

    def _on_clear_history(self):
        self._messages.clear()
        clear_active_messages(self._store)
        save_store(self._store)

    def _on_new_chat(self):
        session = create_session(self._store)
        save_store(self._store)
        self._messages = session["messages"]
        self._panel.clear_messages_view()

    def _on_session_selected(self, session_id: str):
        set_active_session(self._store, session_id)
        save_store(self._store)
        self._messages = get_active_session(self._store)["messages"]
        self._panel.clear_messages_view()
        if self._messages:
            self._panel.load_history(self._messages)

    def _on_session_deleted(self, session_id: str):
        was_active = self._store["active"] == session_id
        delete_session(self._store, session_id)
        save_store(self._store)
        if was_active:
            self._messages = get_active_session(self._store)["messages"]
            self._panel.clear_messages_view()
            if self._messages:
                self._panel.load_history(self._messages)
        self._refresh_session_list()

    def _refresh_session_list(self):
        self._panel.show_session_list(list_sessions(self._store), self._store["active"])

    def _quit(self):
        self._voice.stop()
        self._tray.hide()
        self._app.quit()

    def run(self):
        sys.exit(self._app.exec())


if __name__ == "__main__":
    OrbAssistant().run()
