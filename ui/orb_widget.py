import json
import os
import math
import time

from PyQt6.QtWidgets import QWidget, QApplication, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QCursor
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import (
    glClear, glClearColor, glEnable, glDisable, glBlendFunc,
    glViewport, glUseProgram, glGetUniformLocation, glUniform1f,
    glUniform2f, glGenVertexArrays, glBindVertexArray,
    glDrawArrays, glDeleteProgram,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_BLEND,
    GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_TRIANGLES,
)
from OpenGL.GL.shaders import compileProgram, compileShader, GL_VERTEX_SHADER, GL_FRAGMENT_SHADER

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.json")

VERTEX_SHADER = """
#version 330 core
out vec2 vUV;
void main() {
    vec2 positions[6] = vec2[](
        vec2(-1,-1), vec2(1,-1), vec2(1,1),
        vec2(-1,-1), vec2(1,1), vec2(-1,1)
    );
    vUV = positions[gl_VertexID] * 0.5 + 0.5;
    gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330 core
in vec2 vUV;
out vec4 fragColor;
uniform float uTime;
uniform vec2 uResolution;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1,0));
    float c = hash(i + vec2(0,1));
    float d = hash(i + vec2(1,1));
    return mix(mix(a,b,f.x), mix(c,d,f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 4; i++) {
        v += noise(p) * amp;
        p *= 2.1;
        amp *= 0.5;
    }
    return v;
}

void main() {
    vec2 uv = vUV * 2.0 - 1.0;
    float r2 = dot(uv, uv);

    // Crisp sphere mask
    if (r2 > 1.0) discard;
    float dist = sqrt(r2);

    // True 3-D surface normal from unit sphere
    vec3 N = normalize(vec3(uv, sqrt(1.0 - r2)));

    // Rotating key light — circles the sphere over time
    float lt = uTime * 0.7;
    vec3 L = normalize(vec3(cos(lt) * 0.8, sin(lt * 0.6) * 0.6 + 0.4, sin(lt) * 0.8 + 0.6));

    // Diffuse + Blinn-Phong specular
    float diff = max(dot(N, L), 0.0);
    vec3 V = vec3(0.0, 0.0, 1.0);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 80.0);

    // Soft fill light from opposite side
    float fill = max(dot(N, -L), 0.0) * 0.15;

    // Animated surface texture on the sphere — project onto rotated coords
    // Slow equatorial swirl using spherical-ish UV
    float phi = atan(N.y, N.x) + uTime * 0.25;
    float theta = acos(clamp(N.z, -1.0, 1.0));
    vec2 sphUV = vec2(phi / 6.2832, theta / 3.1416);

    float lava = fbm(sphUV * 4.0 + vec2(uTime * 0.18, uTime * 0.09));
    lava += fbm(sphUV * 8.0 - vec2(uTime * 0.12, uTime * 0.15)) * 0.4;
    lava = clamp(lava / 1.4, 0.0, 1.0);

    // Pulsing breath
    float pulse = 0.5 + 0.5 * sin(uTime * 1.4);

    // Orange palette: dark core -> orange -> bright yellow-white highlights
    vec3 darkOrange  = vec3(0.55, 0.12, 0.01);
    vec3 midOrange   = vec3(0.95, 0.38, 0.02);
    vec3 brightOrange= vec3(1.00, 0.70, 0.20);
    vec3 hotWhite    = vec3(1.00, 0.95, 0.80);

    vec3 surfColor = mix(darkOrange, midOrange, lava);
    surfColor = mix(surfColor, brightOrange, lava * lava);

    // Light the surface
    vec3 color = surfColor * (0.18 + 0.82 * diff + fill);
    color += mix(brightOrange, hotWhite, spec) * spec * 1.2;

    // Subsurface-scatter-like inner glow
    float sss = pow(1.0 - dist, 2.5) * (0.5 + 0.5 * pulse);
    color += midOrange * sss * 0.6;

    // Rim light — orange rim on dark side
    float rim = pow(1.0 - max(dot(N, V), 0.0), 3.5);
    color += vec3(1.0, 0.45, 0.05) * rim * (0.6 + 0.4 * pulse);

    // Smooth sphere edge
    float edge = smoothstep(0.0, 0.04, 1.0 - dist);
    float alpha = edge;

    // Outer glow halo (drawn outside sphere via alpha < 1 region after discard workaround)
    // We already discarded r2>1, so halo is baked into alpha bleed at edge
    // Extra: boost alpha center slightly so it reads as solid
    alpha = clamp(alpha, 0.0, 1.0);

    fragColor = vec4(color, alpha);
}
"""


class OrbGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._shader = None
        self._vao = None
        self._start_time = time.time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # ~60fps

    def initializeGL(self):
        glClearColor(0, 0, 0, 0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._shader = compileProgram(
            compileShader(VERTEX_SHADER, GL_VERTEX_SHADER),
            compileShader(FRAGMENT_SHADER, GL_FRAGMENT_SHADER),
        )
        self._vao = glGenVertexArrays(1)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glUseProgram(self._shader)

        t = time.time() - self._start_time
        glUniform1f(glGetUniformLocation(self._shader, "uTime"), t)
        glUniform2f(
            glGetUniformLocation(self._shader, "uResolution"),
            self.width(), self.height()
        )

        glBindVertexArray(self._vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)

    def cleanup(self):
        if self._shader:
            glDeleteProgram(self._shader)


class OrbWindow(QWidget):
    def __init__(self, on_left_click=None, on_right_click=None):
        super().__init__()
        self._on_left_click = on_left_click
        self._on_right_click = on_right_click
        self._drag_pos = None
        self._dragging = False
        self._press_pos = None

        size = 72
        self.setFixedSize(size, size)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._gl = OrbGLWidget(self)
        self._gl.setGeometry(0, 0, size, size)

        pos = self._load_position()
        self.move(pos)

    def _load_position(self) -> QPoint:
        path = os.path.abspath(CONFIG_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cfg = json.load(f)
                return QPoint(cfg.get("orb_x", 100), cfg.get("orb_y", 100))
            except Exception:
                pass
        screen = QApplication.primaryScreen().geometry()
        return QPoint(screen.width() - 160, screen.height() - 160)

    def _save_position(self):
        path = os.path.abspath(CONFIG_FILE)
        cfg = {}
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cfg = json.load(f)
            except Exception:
                pass
        cfg["orb_x"] = self.x()
        cfg["orb_y"] = self.y()
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = False
        elif event.button() == Qt.MouseButton.RightButton:
            if self._on_right_click:
                self._on_right_click(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos:
            delta = event.globalPosition().toPoint() - self._press_pos
            if delta.manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                self._save_position()
            else:
                if self._on_left_click:
                    self._on_left_click()
            self._dragging = False
            self._drag_pos = None
            self._press_pos = None
