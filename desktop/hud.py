"""Animated native vector display driven by the assistant's actual state."""

import math
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QRadialGradient
from PySide6.QtWidgets import QWidget


class Reactor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "idle"
        self.phase = 0
        self.setMinimumSize(300, 330)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(40)

    def advance(self):
        if self.isVisible():
            self.phase = (self.phase + (1.6 if self.state != "idle" else 0.35)) % 360
            self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#0d2634"), 1))
        for x in range(0, w, 28):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 28):
            p.drawLine(0, y, w, y)
        p.translate(w / 2, h / 2 - 18)
        r = min(w, h - 40) * 0.40
        color = QColor("#ffb65c" if self.state == "error" else "#53e4ff")
        glow = QRadialGradient(0, 0, r * 1.2)
        glow.setColorAt(0, QColor(30, 155, 190, 75))
        glow.setColorAt(0.7, QColor(12, 90, 120, 25))
        glow.setColorAt(1, QColor(5, 14, 24, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-r * 1.2, -r * 1.2, r * 2.4, r * 2.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for scale in (1, 0.91, 0.72, 0.63, 0.42):
            p.setPen(QPen(QColor("#194959"), 1))
            p.drawEllipse(QRectF(-r * scale, -r * scale, 2 * r * scale, 2 * r * scale))
        for i in range(90):
            angle = math.radians(i * 4)
            a, b = r * 1.01, r * (1.06 if i % 5 == 0 else 1.035)
            p.setPen(QPen(color if i % 5 == 0 else QColor("#256276"), 1))
            p.drawLine(
                a * math.cos(angle),
                a * math.sin(angle),
                b * math.cos(angle),
                b * math.sin(angle),
            )
        for scale, width, offset, span in (
            (0.92, 3, 0, 95),
            (0.73, 6, 120, 65),
            (0.63, 2, 240, 110),
        ):
            p.setPen(QPen(color, width))
            rect = QRectF(-r * scale, -r * scale, 2 * r * scale, 2 * r * scale)
            for turn in (0, 180):
                p.drawArc(
                    rect,
                    int((self.phase * (1 if scale > 0.8 else -1) + offset + turn) * 16),
                    span * 16,
                )
        pulse = 1 + (
            0.04 * math.sin(math.radians(self.phase * 4)) if self.state != "idle" else 0
        )
        p.setPen(QPen(color, 2))
        p.drawEllipse(
            QRectF(
                -r * 0.38 * pulse, -r * 0.38 * pulse, r * 0.76 * pulse, r * 0.76 * pulse
            )
        )
        p.setFont(QFont("Helvetica Neue", 20, QFont.Weight.Light))
        p.setPen(color)
        p.drawText(QRectF(-r, -25, 2 * r, 40), Qt.AlignmentFlag.AlignCenter, "FRIDAY")
        p.setFont(QFont("Helvetica Neue", 9))
        label = {
            "idle": "ДАЙЫН",
            "listening": "ТЫҢДАП ТҰРМЫН",
            "thinking": "ОРЫНДАП ЖАТЫРМЫН",
            "speaking": "СӨЙЛЕП ТҰРМЫН",
            "error": "НАЗАР АУДАРЫҢЫЗ",
        }[self.state]
        p.drawText(QRectF(-w / 2, r + 24, w, 28), Qt.AlignmentFlag.AlignCenter, label)
