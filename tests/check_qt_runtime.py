"""Check the Qt binding's None ownership before running long GUI tests.

A short loop is enough to detect the PySide6 6.12.0/CPython 3.11 regression
without exhausting None's reference count and aborting the interpreter.
"""

import sys

import PySide6
import shiboken6
from PySide6.QtGui import QImage, QPainter

print(
    f"Python {sys.version.split()[0]} · PySide6 {PySide6.__version__} · "
    f"Shiboken {shiboken6.__version__}",
    flush=True,
)
image = QImage(8, 8, QImage.Format_ARGB32)
painter = QPainter(image)
try:
    for _ in range(8):
        painter.setRenderHint(QPainter.Antialiasing)
    before = sys.getrefcount(None)
    for _ in range(128):
        painter.setRenderHint(QPainter.Antialiasing)
    delta = sys.getrefcount(None) - before
finally:
    painter.end()
if delta < -64:
    sys.exit(
        f"Broken Qt binding: None reference delta {delta} after 128 void calls. "
        "Reinstall dependencies with: python -m pip install -r requirements.txt"
    )
print(f"PASS: Qt void-call None ownership (reference delta {delta})")
