"""Local Qt artwork and glass-style widgets; no downloaded fonts or assets."""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QCheckBox, QComboBox, QFrame, QGraphicsDropShadowEffect, QWidget


STYLESHEET = """
QWidget { color: #eaf2ff; font-size: 14px; }
QLabel { background: transparent; border: none; }
QLabel#AppTitle { font-size: 26px; font-weight: 700; letter-spacing: 1px; }
QLabel#Subtitle { color: #acbad5; font-size: 13px; }
QLabel#SectionTitle { font-size: 16px; font-weight: 600; color: #eef5ff; }
QLabel#Muted { color: #afbedc; }
QLabel#SiteHint { color: #c5deed; font-size: 13px; }
QLabel#PathValue { font-size: 14px; color: #c0f4f1; }
QLabel#StatusValue { color: #80ead9; font-size: 16px; font-weight: 600; }
QFrame#GlassCard {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(148,181,226,34), stop:1 rgba(155,142,221,21));
    border: 1px solid rgba(197,217,255,51); border-radius: 18px;
}
QPushButton {
    border: 1px solid rgba(207,226,255,65); border-radius: 11px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 rgba(143,181,232,90), stop:1 rgba(99,114,177,65));
    padding: 9px 13px; color: #f0f6ff; font-weight: 600;
}
QPushButton:hover { background: rgba(155,193,243,92); border-color: #8bdde4; }
QPushButton:pressed { background: rgba(58,93,143,180); padding-top: 10px; padding-bottom: 8px; }
QPushButton:focus { border: 2px solid #b2edff; }
QPushButton:disabled { color: #7f8aa8; background: rgba(93,100,140,28); border-color: rgba(160,180,220,25); }
QPushButton#PrimaryButton {
    font-size: 20px; font-weight: 700; border-radius: 28px; border-color: #51e0d1;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #24d69b,stop:1 #118eaa);
}
QPushButton#PrimaryButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #43edb3,stop:1 #20acc6);
}
QPushButton#PrimaryButton:pressed { background: #118c94; }
QPushButton#CancelButton {
    font-size: 19px; font-weight: 600; border-radius: 28px; border-color: #b78cde;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6552c5,stop:1 #b33e9a);
}
QPushButton#CancelButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8270e7,stop:1 #d257b6); }
QPushButton#CancelButton:pressed { background: #774493; }
QPushButton#CancelButton:disabled {
    color: #a99dc3; border-color: rgba(183,140,222,65);
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 rgba(101,82,197,90),stop:1 rgba(179,62,154,70));
}
QPushButton#PrimaryButton:disabled { background: #376f7b; color: #a1bdca; border-color: #508c98; }
QPushButton#UpdateButton {
    border-radius: 12px; padding: 10px 12px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #377b9f,stop:1 #63519d);
}
QLineEdit, QComboBox {
    min-height: 20px; padding: 7px 10px; border-radius: 9px;
    border: 1px solid rgba(194,218,255,62); background: rgba(173,195,231,27);
    color: #edf5ff; selection-background-color: #327f9d;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #79d3e0; background: rgba(173,195,231,42); }
QLineEdit:disabled, QComboBox:disabled { color: #7786a4; background: rgba(100,120,160,12); border-color: rgba(160,180,220,22); }
QComboBox { padding-right: 25px; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox::down-arrow { image: none; border: none; width: 0; height: 0; }
QComboBox QAbstractItemView {
    background: #253554; color: #eaf2ff; selection-background-color: #386888;
    border: 1px solid #5d769b; outline: 0; padding: 5px;
}
QTextEdit {
    background: rgba(233,241,255,235); color: #22334f; border-radius: 12px;
    border: 1px solid rgba(230,239,255,190); padding: 12px;
    selection-background-color: #3a8fa4; selection-color: white;
}
QTextEdit:focus { border: 1px solid #67dfdc; }
QTextEdit#LinkInput { font-size: 15px; color: #22334f; padding: 10px 12px; }
QTextEdit#LogArea { background: rgba(16,24,52,130); color: #cbd7eb; border-color: rgba(184,207,242,38); font-size: 14px; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #8198bb; background: rgba(152,182,224,35); }
QCheckBox::indicator:checked { background: #29c9b2; border-color: #8cf4e3; }
QCheckBox:focus { color: #8ef4e8; }
QProgressBar { border: none; border-radius: 7px; background: rgba(15,25,55,140); height: 14px; }
QProgressBar::chunk {
    border-radius: 7px;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #358aff,stop:0.55 #16c6dc,stop:1 #27e4aa);
}
QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0; }
QScrollBar::handle:vertical { background: rgba(143,173,205,100); min-height: 24px; border-radius: 3px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { color: #edf5ff; background: #243653; border: 1px solid #617493; padding: 7px; }
QMessageBox { background: #17233e; }
"""


def ui_font():
    available = set(QFontDatabase.families())
    for name in ('Microsoft YaHei UI', 'PingFang SC', 'Noto Sans CJK SC', 'Segoe UI'):
        if name in available:
            return QFont(name, 10)
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)


class AuroraWindow(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#0d122d'))
        for x, y, radius, color in ((.25, .18, .8, '#06475e'),
                                     (.91, .06, .75, '#34165d'),
                                     (.64, .94, .6, '#3c165a'),
                                     (1.0, .97, .43, '#086767')):
            gradient = QRadialGradient(QPointF(self.width()*x, self.height()*y), self.width()*radius)
            gradient.setColorAt(0, QColor(color))
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), gradient)


def card(parent=None):
    frame = QFrame(parent)
    frame.setObjectName('GlassCard')
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return frame


def glow(widget, color):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(24)
    effect.setOffset(0, 5)
    effect.setColor(QColor(color))
    widget.setGraphicsEffect(effect)


class ToggleCheckBox(QCheckBox):
    """A painted switch retaining QCheckBox's signals, focus and accessibility."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 0.0
        self.animation = QPropertyAnimation(self, b'position', self)
        self.animation.setDuration(150)
        self.toggled.connect(self._animate)
        self.setMinimumHeight(30)

    @pyqtProperty(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.update()

    def _animate(self, checked):
        self.animation.stop()
        self.animation.setStartValue(self._position)
        self.animation.setEndValue(1.0 if checked else 0.0)
        self.animation.start()

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 58, 30)

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = (self.height()-22)/2
        color = QColor('#27c9b0') if self.isChecked() else QColor('#455776')
        painter.setPen(QPen(QColor('#91c5d4') if self.hasFocus() else QColor('#6d91a7'), 1))
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(0.5, y, 40, 22), 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#f0f7ff'))
        painter.drawEllipse(QRectF(3+self._position*18, y+3, 16, 16))
        painter.setPen(QColor('#eaf2ff') if self.isEnabled() else QColor('#7786a4'))
        painter.setFont(self.font())
        painter.drawText(self.rect().adjusted(51, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.text())


class GlassComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#d7e8ff') if self.isEnabled() else QColor('#7786a4'),
                            1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        x, y = self.width()-17, self.height()/2
        painter.drawLine(QPointF(x-4, y-2), QPointF(x, y+2))
        painter.drawLine(QPointF(x, y+2), QPointF(x+4, y-2))


def line_icon(kind, color='#bbecfa', size=24):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size/24, size/24)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    paths = {
        'download': [[(12,3),(12,15)],[(7,10),(12,15),(17,10)],[(4,16),(4,21),(20,21),(20,16)]],
        'folder': [[(3,19),(3,6),(9,6),(11,9),(21,9),(21,19),(3,19)]],
        'open': [[(3,19),(3,6),(9,6),(11,9),(21,9),(21,19),(3,19)],[(8,14),(16,14)],[(13,11),(16,14),(13,17)]],
        'file': [[(6,3),(14,3),(19,8),(19,21),(6,21),(6,3)],[(14,3),(14,8),(19,8)],[(9,12),(16,12)],[(9,16),(16,16)]],
        'close': [[(6,6),(18,18)],[(18,6),(6,18)]],
        'pause': [[(8,5),(8,19)],[(16,5),(16,19)]],
        'link': [[(9,15),(15,9)],[(7,10),(4,13),(4,17),(7,20),(11,20),(14,17)],[(10,7),(13,4),(17,4),(20,7),(20,11),(17,14)]],
        'tune': [[(5,4),(5,20)],[(12,4),(12,20)],[(19,4),(19,20)],[(2,8),(8,8)],[(9,15),(15,15)],[(16,9),(22,9)]],
        'cloud': [[(5,17),(3,15),(3,12),(6,9),(9,9),(10,5),(14,4),(18,6),(19,10),(22,12),(22,15),(20,17)],[(12,21),(12,12)],[(8,16),(12,12),(16,16)]],
        'check': [[(5,12),(10,17),(19,7)]],
    }
    if kind == 'youtube':
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#e5efff'))
        painter.drawRoundedRect(QRectF(1,4,22,16), 5, 5)
        painter.setBrush(QColor('#172345'))
        path = QPainterPath(QPointF(10,8))
        path.lineTo(16,12)
        path.lineTo(10,16)
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == 'gauge':
        painter.drawArc(QRectF(3,3,18,18), 20*16, 300*16)
        painter.drawLine(QPointF(12,12), QPointF(19,5))
    else:
        for points in paths.get(kind, paths['file']):
            path = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                path.lineTo(*point)
            painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)
