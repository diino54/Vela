"""Small, shared layout primitives. These create widgets, never persist state."""
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout


def section(parent, title):
    group = QVBoxLayout()
    group.setContentsMargins(0, 0, 0, 0)
    group.setSpacing(12)
    heading = QLabel(title)
    heading.setObjectName('sectionTitle')
    group.addWidget(heading)
    parent.addLayout(group)
    return group

def divider(parent, spacing=24):
    parent.addSpacing(spacing)
    line = QFrame()
    line.setObjectName('sectionDivider')
    line.setFixedHeight(1)
    parent.addWidget(line)
    parent.addSpacing(spacing)
# 2. Customization navigation and application/limiter controls.
