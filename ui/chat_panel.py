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
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self._is_user = is_user
        self._label = QLabel(text)
        self._label.setWordWrap(True)
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
                    border-radius: 12px;
                    padding: 8px 12px;
                }
            """)
        else:
            row.addWidget(self._label)
            row.addStretch()
            self._label.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    background: #1A1A1A;
                    border-radius: 12px;
                    border: 1px solid #333333;
                    padding: 8px 12px;
                }
            """)
        self.setStyleSheet("QFrame { background: transparent; }")

    def append_text(self, chunk: str):
        self._label.setText(self._label.text() + chunk)

    def set_text(self, text: str):
        self._label.setText(text)


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


class ChatPanel(QWidget):
    message_submitted = pyqtSignal(str)

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

        self._min_btn = QPushButton("－")
        self._min_btn.setFixedSize(26, 22)
        self._min_btn.setToolTip("Minimize")
        self._min_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._min_btn.setStyleSheet("""
            QPushButton {
                background: #222222; color: #888888;
                border: none; border-radius: 4px; font-size: 13px;
            }
            QPushButton:hover { background: #333333; color: #FFFFFF; }
        """)
        self._min_btn.clicked.connect(self._toggle_minimize)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedSize(44, 22)
        self._clear_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: #222222; color: #888888;
                border: none; border-radius: 4px; font-size: 10px;
            }
            QPushButton:hover { background: #333333; color: #FFFFFF; }
        """)
        self._clear_btn.clicked.connect(self._on_clear)

        hl.addWidget(self._clear_btn)
        hl.addWidget(self._min_btn)
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

        # Loading
        self._loading = QLabel("thinking…")
        self._loading.setFont(QFont("Segoe UI", 9))
        self._loading.setStyleSheet("color: #555555; background: transparent;")
        self._loading.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._loading.hide()
        body_layout.addWidget(self._loading)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #222222; background: #222222; max-height: 1px;")
        body_layout.addWidget(div)

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
        body_layout.addLayout(input_row)

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

    def add_user_message(self, text: str):
        bubble = MessageBubble(text, is_user=True)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def start_assistant_message(self):
        self._loading.hide()
        bubble = MessageBubble("", is_user=False)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        self._current_bubble = bubble
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
        err = MessageBubble(f"Error: {msg}", is_user=False)
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, err)
        self._scroll_to_bottom()

    def _on_clear(self):
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.clear_history_requested()

    def clear_history_requested(self):
        pass

    def load_history(self, messages: list[dict]):
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
            if role == "user":
                bubble = MessageBubble(content, is_user=True)
            elif role == "assistant":
                bubble = MessageBubble(content, is_user=False)
            else:
                continue
            self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def reposition_near_orb(self, orb_pos, orb_size, screen_rect):
        pw, ph = self.width(), self.height()
        ox, oy, ow = orb_pos.x(), orb_pos.y(), orb_size.width()
        x = ox - pw - 10
        if x < screen_rect.left():
            x = ox + ow + 10
        y = max(screen_rect.top(), min(oy, screen_rect.bottom() - ph))
        self.setGeometry(x, y, pw, ph)
