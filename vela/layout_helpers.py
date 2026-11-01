"""Shared layout primitives; collapsible state is delegated to sections.py."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def section(parent, title, *, preferences=None, key=None):
    if preferences is not None:
        from .sections import CollapsibleSection

        panel = CollapsibleSection(title, preferences, key)
        parent.addWidget(panel)
        panel.body_layout.section_widget = panel
        return panel.body_layout
    group = QVBoxLayout()
    group.setContentsMargins(0, 0, 0, 0)
    group.setSpacing(12)
    heading = QLabel(title)
    heading.setObjectName("sectionTitle")
    group.addWidget(heading)
    parent.addLayout(group)
    return group


def divider(parent, spacing=24):
    parent.addSpacing(spacing)
    line = QFrame()
    line.setObjectName("sectionDivider")
    line.setFixedHeight(1)
    parent.addWidget(line)
    parent.addSpacing(spacing)


# 2. Customization navigation and application/limiter controls.
