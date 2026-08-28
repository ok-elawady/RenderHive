import sys
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QPixmap, QPainter, QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

key_svg = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
    '<path d="m21 2-9.6 9.6"/>'
    '<circle cx="7.5" cy="15.5" r="5.5"/>'
    '</svg>'
)

renderer = QSvgRenderer(QByteArray(key_svg.encode("utf-8")))
print(f"Renderer valid: {renderer.isValid()}")

pixmap = QPixmap(16, 16)
pixmap.fill(Qt.transparent) if hasattr(Qt, 'transparent') else None
painter = QPainter(pixmap)
renderer.render(painter)
painter.end()

print(f"Pixmap isNull: {pixmap.isNull()}")
