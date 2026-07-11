from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QTextEdit, QPushButton, QFrame, QSizeGrip,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPoint, QRect, QEvent
from PyQt6.QtGui import QKeyEvent, QFont, QPainter, QColor, QPen, QBrush, QPainterPath


class _StreamSignals(QObject):
    token = pyqtSignal(str)
    done  = pyqtSignal()
    error = pyqtSignal(str)
    start = pyqtSignal()


class MessageBubble(QFrame):
    def __init__(self, text: str, is_user: bool, max_width: int = 260, parent=None):
        super().__init__(parent)
        self._is_user = is_user
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(max_width)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setFont(QFont("Segoe UI", 10))
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        if is_user:
            row.addStretch()
            row.addWidget(self._label)
            self._label.setStyleSheet("""
                QLabel {
                    color: #000000;
                    background: #F0F0F0;
                    border-radius: 14px;
                    padding: 8px 13px;
                }
            """)
        else:
            row.addWidget(self._label)
            row.addStretch()
            self._label.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    background: #1A1A1A;
                    border-radius: 14px;
                    border: 1px solid #333333;
                    padding: 8px 13px;
                }
            """)
        self.setStyleSheet("QFrame { background: transparent; }")

    def append_text(self, chunk: str):
        self._label.setText(self._label.text() + chunk)

    def set_text(self, text: str):
        self._label.setText(text)

    def set_max_width(self, max_width: int):
        self._label.setMaximumWidth(max_width)


class ChatInput(QTextEdit):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setFont(QFont("Segoe UI", 10))
        self.setPlaceholderText("Ask anything…")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("""
            QTextEdit {
                background: #111111;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: #444444;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            text = self.toPlainText().strip()
            if text:
                self.submitted.emit(text)
                self.clear()
        else:
            super().keyPressEvent(event)


_GRIP = 6
_EDGE_NONE   = 0
_EDGE_LEFT   = 1
_EDGE_RIGHT  = 2
_EDGE_TOP    = 4
_EDGE_BOTTOM = 8


class SessionItem(QFrame):
    clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)

    def __init__(self, session_id: str, title: str, subtitle: str, is_active: bool, parent=None):
        super().__init__(parent)
        self._id = session_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        bg = "#1D1D1D" if is_active else "transparent"
        self.setStyleSheet(f"""
            QFrame {{ background: {bg}; border-radius: 8px; }}
            QFrame:hover {{ background: #1D1D1D; }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 8, 8)
        row.setSpacing(6)

        col = QVBoxLayout()
        col.setSpacing(1)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        title_lbl.setStyleSheet("color: #EEEEEE; background: transparent;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont("Segoe UI", 8))
        sub_lbl.setStyleSheet("color: #666666; background: transparent;")
        col.addWidget(title_lbl)
        col.addWidget(sub_lbl)
        row.addLayout(col)
        row.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setCursor(Qt.CursorShape.ArrowCursor)
        del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #555555; border: none; font-size: 10px; }
            QPushButton:hover { color: #FF5F57; }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._id))
        row.addWidget(del_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._id)
        super().mousePressEvent(event)


class ChatPanel(QWidget):
    message_submitted = pyqtSignal(str)
    new_chat_requested = pyqtSignal()
    session_selected = pyqtSignal(str)
    session_delete_requested = pyqtSignal(str)
    history_opened = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(320, 300)
        self.resize(380, 560)
        self.setMouseTracking(True)

        self._drag_pos: QPoint | None = None
        self._resize_edge = _EDGE_NONE
        self._resize_origin: QPoint | None = None
        self._resize_start_geom: QRect | None = None
        self._minimized = False
        self._full_height = 560

        self._stream_signals = _StreamSignals()
        self._stream_signals.start.connect(self.start_assistant_message)
        self._stream_signals.token.connect(self._on_token)
        self._stream_signals.done.connect(self._on_stream_done)
        self._stream_signals.error.connect(self._on_stream_error)
        self._current_bubble: MessageBubble | None = None
        self._streaming = False
        self._bubbles: list[MessageBubble] = []

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._container = QFrame(self)
        self._container.setObjectName("container")
        self._container.setStyleSheet("""
            QFrame#container {
                background: #0A0A0A;
                border-radius: 14px;
                border: 1px solid #2A2A2A;
            }
        """)
        outer.addWidget(self._container)

        root = QVBoxLayout(self._container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        self._header = QFrame()
        self._header.setObjectName("hdr")
        self._header.setFixedHeight(44)
        self._header.setStyleSheet("""
            QFrame#hdr {
                background: #111111;
                border-radius: 0px;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid #222222;
            }
        """)
        self._header.setCursor(Qt.CursorShape.SizeAllCursor)
        self._header.installEventFilter(self)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        dot_row = QHBoxLayout()
        dot_row.setSpacing(5)
        for color in ("#FF5F57", "#FEBC2E", "#28C840"):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            dot_row.addWidget(dot)
        hl.addLayout(dot_row)

        title = QLabel("Orb Assistant")
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        title.setStyleSheet("color: #AAAAAA; background: transparent; letter-spacing: 0.5px;")
        hl.addWidget(title)
        hl.addStretch()

        _icon_btn_style = """
            QPushButton {{
                background: #1C1C1C; color: #888888;
                border: none; border-radius: 6px; font-size: {size}px;
            }}
            QPushButton:hover {{ background: #2E2E2E; color: #FFFFFF; }}
        """

        def _make_icon_btn(icon: str, tooltip: str, font_size: int = 12) -> QPushButton:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 26)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.ArrowCursor)
            btn.setStyleSheet(_icon_btn_style.format(size=font_size))
            return btn

        self._history_btn = _make_icon_btn("☰", "Chat history")
        self._history_btn.clicked.connect(self._toggle_history_view)

        self._new_btn = _make_icon_btn("＋", "New chat", font_size=14)
        self._new_btn.clicked.connect(self._on_new_chat)

        self._clear_btn = _make_icon_btn("⟲", "Clear this chat", font_size=13)
        self._clear_btn.clicked.connect(self._on_clear)

        self._min_btn = _make_icon_btn("－", "Minimize")
        self._min_btn.clicked.connect(self._toggle_minimize)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addWidget(self._history_btn)
        btn_row.addWidget(self._new_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._min_btn)
        hl.addLayout(btn_row)
        root.addWidget(self._header)

        # ── Body (collapsible) ────────────────────────────────────────
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(12, 10, 12, 10)
        body_layout.setSpacing(8)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #111111; width: 4px; border-radius: 2px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #444444; border-radius: 2px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._messages_widget = QWidget()
        self._messages_widget.setStyleSheet("background: transparent;")
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setSpacing(10)
        self._messages_layout.setContentsMargins(2, 2, 2, 2)
        self._messages_layout.addStretch()
        self._scroll.setWidget(self._messages_widget)
        body_layout.addWidget(self._scroll)

        # History (session list) overlay
        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._history_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #111111; width: 4px; border-radius: 2px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #444444; border-radius: 2px; min-height: 20px;
            }
        """)
        self._history_list_widget = QWidget()
        self._history_list_widget.setStyleSheet("background: transparent;")
        self._history_layout = QVBoxLayout(self._history_list_widget)
        self._history_layout.setSpacing(4)
        self._history_layout.setContentsMargins(2, 2, 2, 2)
        self._history_layout.addStretch()
        self._history_scroll.setWidget(self._history_list_widget)
        self._history_scroll.hide()
        body_layout.addWidget(self._history_scroll)
        self._showing_history = False

        # Loading
        self._loading = QLabel("thinking…")
        self._loading.setFont(QFont("Segoe UI", 9))
        self._loading.setStyleSheet("color: #555555; background: transparent;")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._loading.hide()
        body_layout.addWidget(self._loading)

        # Divider
        self._div = QFrame()
        self._div.setFrameShape(QFrame.Shape.HLine)
        self._div.setStyleSheet("color: #222222; background: #222222; max-height: 1px;")
        body_layout.addWidget(self._div)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = ChatInput()
        self._input.submitted.connect(self._handle_submit)

        self._send_btn = QPushButton("↑")
        self._send_btn.setFixedSize(42, 42)
        self._send_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF; color: #000000;
                border: none; border-radius: 8px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background: #DDDDDD; }
            QPushButton:disabled { background: #222222; color: #555555; }
        """)
        self._send_btn.clicked.connect(self._send_from_button)

        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)
        self._input_wrap = QWidget()
        self._input_wrap.setLayout(input_row)
        body_layout.addWidget(self._input_wrap)

        # Resize grip
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 2, 0)
        grip_row.addStretch()
        size_grip = QSizeGrip(self)
        size_grip.setStyleSheet("background: transparent;")
        grip_row.addWidget(size_grip)
        body_layout.addLayout(grip_row)

        root.addWidget(self._body)

    # ── Minimize ──────────────────────────────────────────────────────

    def _toggle_minimize(self):
        if self._minimized:
            self._body.show()
            self.setMinimumHeight(300)
            self.resize(self.width(), self._full_height)
            self._min_btn.setText("－")
        else:
            self._full_height = self.height()
            self._body.hide()
            self.setMinimumHeight(0)
            self.resize(self.width(), self._header.height() + 2)
            self._min_btn.setText("＋")
        self._minimized = not self._minimized

    # ── Drag via header ───────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._header:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.Type.MouseMove and self._drag_pos is not None:
                if event.buttons() & Qt.MouseButton.LeftButton:
                    self.move(event.globalPosition().toPoint() - self._drag_pos)
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_pos = None
                return True
        return super().eventFilter(obj, event)

    # ── Edge resize ───────────────────────────────────────────────────

    def _detect_edge(self, pos: QPoint) -> int:
        x, y, w, h = pos.x(), pos.y(), self.width(), self.height()
        edge = _EDGE_NONE
        if x <= _GRIP:           edge |= _EDGE_LEFT
        if x >= w - _GRIP:       edge |= _EDGE_RIGHT
        if y <= _GRIP:           edge |= _EDGE_TOP
        if y >= h - _GRIP:       edge |= _EDGE_BOTTOM
        return edge

    def _edge_cursor(self, edge: int) -> Qt.CursorShape:
        return {
            _EDGE_LEFT | _EDGE_TOP:     Qt.CursorShape.SizeFDiagCursor,
            _EDGE_RIGHT | _EDGE_BOTTOM: Qt.CursorShape.SizeFDiagCursor,
            _EDGE_RIGHT | _EDGE_TOP:    Qt.CursorShape.SizeBDiagCursor,
            _EDGE_LEFT | _EDGE_BOTTOM:  Qt.CursorShape.SizeBDiagCursor,
            _EDGE_LEFT:                 Qt.CursorShape.SizeHorCursor,
            _EDGE_RIGHT:                Qt.CursorShape.SizeHorCursor,
            _EDGE_TOP:                  Qt.CursorShape.SizeVerCursor,
            _EDGE_BOTTOM:               Qt.CursorShape.SizeVerCursor,
        }.get(edge, Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._detect_edge(event.position().toPoint())
            if edge != _EDGE_NONE:
                self._resize_edge = edge
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_start_geom = self.geometry()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if event.buttons() & Qt.MouseButton.LeftButton and self._resize_edge != _EDGE_NONE:
            delta = event.globalPosition().toPoint() - self._resize_origin
            geo = QRect(self._resize_start_geom)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            if self._resize_edge & _EDGE_RIGHT:  geo.setRight(geo.right() + delta.x())
            if self._resize_edge & _EDGE_BOTTOM: geo.setBottom(geo.bottom() + delta.y())
            if self._resize_edge & _EDGE_LEFT:
                nl = geo.left() + delta.x()
                if geo.right() - nl >= min_w: geo.setLeft(nl)
            if self._resize_edge & _EDGE_TOP:
                nt = geo.top() + delta.y()
                if geo.bottom() - nt >= min_h: geo.setTop(nt)
            self.setGeometry(geo)
        else:
            self.setCursor(self._edge_cursor(self._detect_edge(pos)))

    def mouseReleaseEvent(self, event):
        self._resize_edge = _EDGE_NONE
        self._resize_origin = None
        self._resize_start_geom = None

    # ── Chat public API ───────────────────────────────────────────────

    def _send_from_button(self):
        text = self._input.toPlainText().strip()
        if text:
            self._input.clear()
            self._handle_submit(text)

    def _handle_submit(self, text: str):
        if self._streaming:
            return
        self.message_submitted.emit(text)

    def _bubble_max_width(self) -> int:
        w = self._scroll.viewport().width() or (self.width() - 40)
        return max(140, int(w * 0.76))

    def _add_bubble(self, text: str, is_user: bool) -> "MessageBubble":
        bubble = MessageBubble(text, is_user=is_user, max_width=self._bubble_max_width())
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        return bubble

    def add_user_message(self, text: str):
        self._add_bubble(text, is_user=True)
        self._scroll_to_bottom()

    def start_assistant_message(self):
        self._loading.hide()
        self._current_bubble = self._add_bubble("", is_user=False)
        self._streaming = True
        self._send_btn.setEnabled(False)
        self._scroll_to_bottom()

    def show_loading(self):
        self._loading.show()
        self._streaming = True
        self._send_btn.setEnabled(False)

    def stream_start(self):  self._stream_signals.start.emit()
    def stream_token(self, token: str): self._stream_signals.token.emit(token)
    def stream_done(self):   self._stream_signals.done.emit()
    def stream_error(self, msg: str): self._stream_signals.error.emit(msg)

    def _on_token(self, token: str):
        if self._current_bubble is not None:
            self._current_bubble.append_text(token)
        self._scroll_to_bottom()

    def _on_stream_done(self):
        self._streaming = False
        self._current_bubble = None
        self._send_btn.setEnabled(True)
        self._loading.hide()

    def _on_stream_error(self, msg: str):
        self._streaming = False
        self._current_bubble = None
        self._send_btn.setEnabled(True)
        self._loading.hide()
        self._add_bubble(f"Error: {msg}", is_user=False)
        self._scroll_to_bottom()

    def _on_clear(self):
        self.clear_messages_view()
        self.clear_history_requested()

    def clear_history_requested(self):
        pass

    # ── Session history ──────────────────────────────────────────────

    def _toggle_history_view(self):
        if self._showing_history:
            self._hide_history_view()
        else:
            self._history_btn.setText("💬")
            self._history_btn.setToolTip("Back to chat")
            self._scroll.hide()
            self._loading.hide()
            self._div.hide()
            self._input_wrap.hide()
            self._history_scroll.show()
            self._showing_history = True
            self.history_opened.emit()

    def _hide_history_view(self):
        self._history_btn.setText("☰")
        self._history_btn.setToolTip("Chat history")
        self._history_scroll.hide()
        self._scroll.show()
        self._div.show()
        self._input_wrap.show()
        self._showing_history = False

    def _on_new_chat(self):
        self._hide_history_view()
        self.new_chat_requested.emit()

    def show_session_list(self, sessions: list[dict], active_id: str):
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for s in sessions:
            item = SessionItem(
                s["id"], s["title"], s.get("updated_at", "")[:16].replace("T", " "),
                is_active=(s["id"] == active_id),
            )
            item.clicked.connect(self._on_session_clicked)
            item.delete_clicked.connect(self.session_delete_requested.emit)
            self._history_layout.insertWidget(self._history_layout.count() - 1, item)

    def _on_session_clicked(self, session_id: str):
        self._hide_history_view()
        self.session_selected.emit(session_id)

    def clear_messages_view(self):
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._bubbles.clear()

    def load_history(self, messages: list[dict]):
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            if role not in ("user", "assistant"):
                continue
            self._add_bubble(content, is_user=(role == "user"))
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._bubbles:
            mw = self._bubble_max_width()
            for bubble in self._bubbles:
                bubble.set_max_width(mw)

    def reposition_near_orb(self, orb_pos, orb_size, screen_rect):
        pw, ph = self.width(), self.height()
        ox, oy, ow = orb_pos.x(), orb_pos.y(), orb_size.width()
        x = ox - pw - 10
        if x < screen_rect.left():
            x = ox + ow + 10
        y = max(screen_rect.top(), min(oy, screen_rect.bottom() - ph))
        self.setGeometry(x, y, pw, ph)
