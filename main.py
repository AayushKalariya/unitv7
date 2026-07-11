import sys
import os
import threading

from dotenv import load_dotenv
load_dotenv()

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtCore import Qt, QSize

from ui.orb_widget import OrbWindow
from ui.chat_panel import ChatPanel
from services.claude_api import stream_response
from services.calendar_api import get_upcoming_events, format_events_for_prompt
from storage.history import load_history, save_history, clear_history


def make_tray_icon() -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill(QColor(100, 50, 200))
    return QIcon(pix)


class OrbAssistant:
    def __init__(self):
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)

        self._messages: list[dict] = load_history()
        self._panel_visible = False

        self._orb = OrbWindow(
            on_left_click=self._toggle_panel,
            on_right_click=self._show_tray_menu,
        )

        self._panel = ChatPanel()
        self._panel.message_submitted.connect(self._on_message)
        self._panel.clear_history_requested = self._on_clear_history

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

    def _stream_reply(self):
        try:
            events = get_upcoming_events(max_results=10)
            calendar_ctx = format_events_for_prompt(events)

            full_text = ""
            first = True

            for token in stream_response(self._messages, calendar_ctx):
                if first:
                    self._panel.stream_start()
                    first = False
                full_text += token
                self._panel.stream_token(token)

            self._panel.stream_done()

            self._messages.append({"role": "assistant", "content": full_text})
            save_history(self._messages)

        except Exception as e:
            self._panel.stream_error(str(e))
            if self._messages and self._messages[-1]["role"] == "user":
                self._messages.pop()

    def _on_clear_history(self):
        self._messages.clear()
        clear_history()

    def _quit(self):
        self._tray.hide()
        self._app.quit()

    def run(self):
        sys.exit(self._app.exec())


if __name__ == "__main__":
    OrbAssistant().run()
