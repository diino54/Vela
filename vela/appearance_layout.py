"""Build metrics and appearance controls in the left customization column.

Each dictionary is keyed by the actual MangoHud option name. Defaults and
ranges remain identical to the controller's existing managed configuration.
Callbacks call Window actions; only those actions decide when to persist.
"""
from pathlib import Path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractSpinBox, QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from . import mangohud
from .runtime import available as textured_runtime_available
from .controls import NoWheelSpinBox, DependencyRow, NumberControl
from .layout_helpers import section, divider


def build_customization(window, panel):
    """Install metric/appearance/text/font controls and return their layout."""
    # 3. Metrics, typography, background, border and shadow controls.
    window.simple_panel = QWidget()
    simple_layout = QVBoxLayout(window.simple_panel)
    simple_layout.setContentsMargins(0, 0, 0, 0)
    simple_layout.setSpacing(0)
    panel.addWidget(window.simple_panel)
    metrics_section = section(simple_layout, 'Metrics')
    window.metric_controls = {}
    def metric_checkbox(group, key, label):
        checkbox = QCheckBox(label)
        checkbox.setChecked(mangohud.metric_values('')[key])
        checkbox.setToolTip(key)
        group.addWidget(checkbox)
        window.metric_controls[key] = checkbox

    for key, label in (('fps', 'FPS'), ('frametime', 'Frame time'),
                       ('frame_timing', 'Frame time graph')):
        if key == 'frametime':
            metrics_section.addSpacing(6)
        metric_checkbox(metrics_section, key, label)
    divider(simple_layout)
    hardware_section = section(simple_layout, 'Hardware')
    for parent_key, child_key, name in (('gpu_stats', 'gpu_temp', 'GPU'),
                                         ('cpu_stats', 'cpu_temp', 'CPU')):
        if parent_key == 'cpu_stats':
            hardware_section.addSpacing(6)
        metric_checkbox(hardware_section, parent_key, f'{name} usage')
        temperature = QCheckBox(f'{name} temperature')
        temperature.setChecked(False)
        temperature.setToolTip(child_key)
        window.metric_controls[child_key] = temperature
        hardware_section.addWidget(DependencyRow(window.metric_controls[parent_key], temperature))
    hardware_section.addSpacing(6)
    metric_checkbox(hardware_section, 'ram', 'RAM usage')
    metric_checkbox(hardware_section, 'vram', 'VRAM usage')
    divider(simple_layout)
    misc_section = section(simple_layout, 'Miscellaneous')
    for key, label in (('gamemode', 'GameMode status'), ('vkbasalt', 'vkBasalt status'),
                       ('engine_version', 'Graphics API / engine'),
                       ('vulkan_driver', 'Vulkan driver'), ('wine', 'Wine / Proton version')):
        if key == 'engine_version':
            misc_section.addSpacing(6)
        metric_checkbox(misc_section, key, label)
    window.metric_controls['gamemode'].setToolTip('Show whether GameMode is active; does not enable GameMode.')
    window.metric_controls['vkbasalt'].setToolTip('Show whether vkBasalt is active; does not enable vkBasalt.')
    divider(simple_layout)
    window.appearance_controls = {}
    window.color_controls = {}
    window.text_controls = {}
    window.font_controls = {}
    for title, color_key, color_default, fields in (
        ('Text', 'text_color', 'FFFFFF', (
            ('font_size', 'Font size', 8, 48, 24, ' px'),
            ('font_scale', 'Font scale', .5, 3, 1, ' ×'),
            ('font_size_text', 'Additional text size', 8, 48, 24, ' px'),
            ('text_outline_thickness', 'Outline thickness', .1, 5, 1.5, ' px'),
            ('alpha', 'Text opacity', 0, 100, 100, ' %'))),
        ('Background', 'background_color', '020202', (
            ('background_alpha', 'Background opacity', 0, 100, 50, ' %'),
            ('round_corners', 'Corner radius', 0, 30, 0, ' px'),
            ('vela_padding', 'Padding', 0, 64, 5, ' px'),
            ('vela_background_blur', 'Background blur', 0, 32, 0, ' px'),
            ('vela_background_noise', 'Noise opacity', 0, 100, 0, ' %'))),
        ('Border', 'vela_border_color', '414141', (
            ('vela_border_width', 'Border width', 0, 8, 0, ' px'),
            ('vela_border_alpha', 'Border opacity', 0, 100, 100, ' %'))),
        ('Shadow', 'vela_shadow_color', '000000', (
            ('vela_shadow_alpha', 'Shadow opacity', 0, 100, 0, ' %'),
            ('vela_shadow_blur', 'Softness', 0, 40, 16, ' px'),
            ('vela_shadow_offset_x', 'Horizontal offset', -40, 40, 0, ' px'),
            ('vela_shadow_offset_y', 'Vertical offset', -40, 40, 4, ' px'))),
    ):
        group = section(simple_layout, title)
        if title == 'Text':
            for key, label in (('font_file', 'Font'), ('font_file_text', 'Additional text font')):
                group.addWidget(QLabel(label))
                row = QHBoxLayout()
                row.setSpacing(6)
                choose = QPushButton()
                choose.setMinimumWidth(0)
                choose.setAccessibleName(label)
                window.font_controls[key] = choose
                window.set_customization_font(key, '')
                choose.clicked.connect(lambda checked=False, key=key: window.choose_customization_font(key))
                if key == 'font_file_text':
                    choose.setContextMenuPolicy(Qt.CustomContextMenu)
                    choose.customContextMenuRequested.connect(lambda pos, key=key: window.show_font_file_menu(key, pos))
                reset = QPushButton()
                reset.setIcon(QIcon(str(Path(__file__).parent / 'assets/reset.svg')))
                reset.setIconSize(QSize(16, 16))
                reset.setFixedWidth(32)
                reset.setAccessibleName(f'Reset {label.lower()}')
                reset.setToolTip('Restore default font' if key == 'font_file' else 'Use the main font')
                reset.clicked.connect(lambda checked=False, key=key: window.reset_customization_font(key))
                row.addWidget(choose, 1)
                presets = QPushButton()
                presets.setIcon(QIcon(str(Path(__file__).parent / 'assets/fonts.svg')))
                presets.setIconSize(QSize(18, 18))
                presets.setFixedWidth(32)
                presets.setAccessibleName(f'Font presets for {label.lower()}')
                presets.setToolTip('Browse downloadable fonts and weights')
                presets.clicked.connect(lambda checked=False, key=key: window.open_font_catalog(key))
                row.addWidget(presets)
                row.addWidget(reset)
                group.addLayout(row)
        group.addWidget(QLabel('Color'))
        button = QPushButton()
        button.setAccessibleName(f'{title} color')
        button.setToolTip(color_key)
        window.color_controls[color_key] = button
        window.set_customization_color(color_key, color_default)
        button.clicked.connect(lambda checked=False, key=color_key: window.choose_customization_color(key))
        group.addWidget(button)
        for key, label, minimum, maximum, default, suffix in fields:
            group.addSpacing(6)
            field = NoWheelSpinBox()
            field.setDecimals(1 if key in ('font_scale', 'text_outline_thickness', 'vela_background_noise', 'vela_border_width') else 0)
            field.setSingleStep(.1 if key in ('font_scale', 'text_outline_thickness', 'vela_border_width') else 1)
            field.setRange(minimum, maximum)
            field.setValue(default)
            field.setSuffix(suffix)
            if key in ('vela_border_width', 'vela_shadow_alpha', 'vela_background_blur'):
                field.setSpecialValueText('Off')
            field.setButtonSymbols(QAbstractSpinBox.NoButtons)
            field.setFocusPolicy(Qt.StrongFocus)
            field.setAccessibleName(label)
            field.setToolTip(key)
            group.addWidget(QLabel(label))
            group.addWidget(NumberControl(field))
            window.appearance_controls[key] = field
        if title == 'Text':
            window.appearance_controls['font_size_text'].setToolTip('Size of additional text such as media player metadata (font_size_text).')
            for key, label, default in (('no_small_font', 'Full-size units', False),
                                         ('text_outline', 'Text outline', True)):
                checkbox = QCheckBox(label)
                checkbox.setChecked(default)
                checkbox.setToolTip(key)
                window.text_controls[key] = checkbox
                group.addWidget(checkbox)
            outline_color = QPushButton()
            outline_color.setAccessibleName('Text outline color')
            window.color_controls['text_outline_color'] = outline_color
            window.set_customization_color('text_outline_color', '000000')
            outline_color.clicked.connect(lambda: window.choose_customization_color('text_outline_color'))
            group.addWidget(QLabel('Outline color'))
            group.addWidget(outline_color)
            window.text_controls['text_outline'].toggled.connect(outline_color.setEnabled)
            window.text_controls['text_outline'].toggled.connect(window.appearance_controls['text_outline_thickness'].setEnabled)
            divider(simple_layout)
        elif title == 'Background':
            window.appearance_controls['vela_background_blur'].setToolTip(
                'Experimental GPU blur of the game behind the HUD; 0 disables it. Requires desktop OpenGL 3+ or a compatible SDR Vulkan swapchain. Lower background opacity to see it.')
            window.appearance_controls['vela_padding'].setToolTip(
                'Equal inner spacing on all sides. The panel grows to preserve content width; the HUD anchor stays fixed. Thick borders keep a safe minimum inset. Requires Vela MangoHud.')
            window.appearance_controls['vela_background_noise'].setToolTip(
                'Opacity of a subtle, low-contrast grain layer. 0% is invisible; 100% shows the full texture. Requires Vela MangoHud.')
            if not textured_runtime_available():
                window.appearance_controls['vela_background_noise'].editing_container.setEnabled(False)
                window.appearance_controls['vela_padding'].editing_container.setEnabled(False)
                window.appearance_controls['vela_background_blur'].editing_container.setEnabled(False)
            hint = QLabel('Experimental · Vela MangoHud required for games.')
            hint.setWordWrap(True)
            hint.setStyleSheet('color: #999999; font-size: 11px;')
            group.addWidget(hint)
            divider(simple_layout)
        elif title == 'Border':
            button.setToolTip('Border color; set Border width above 0 px to enable. Requires Vela MangoHud.')
            window.appearance_controls['vela_border_width'].setToolTip(
                'HUD border thickness; 0 px disables the border. Uses Background corner radius. Requires Vela MangoHud.')
            window.appearance_controls['vela_border_alpha'].setToolTip(
                'Border opacity, independent of the background opacity.')
            if not textured_runtime_available():
                button.setEnabled(False)
                for key in ('vela_border_width', 'vela_border_alpha'):
                    window.appearance_controls[key].editing_container.setEnabled(False)
            divider(simple_layout)
        else:
            button.setToolTip('Color of the soft shadow behind the HUD. Requires Vela MangoHud.')
            window.appearance_controls['vela_shadow_alpha'].setToolTip('Shadow opacity; 0% disables the shadow.')
            window.appearance_controls['vela_shadow_blur'].setToolTip('Shadow softness; 0 px gives a hard edge.')
            window.appearance_controls['vela_shadow_offset_x'].setToolTip('Negative moves left, positive moves right.')
            window.appearance_controls['vela_shadow_offset_y'].setToolTip('Negative moves up, positive moves down.')
            if not textured_runtime_available():
                button.setEnabled(False)
                for key in ('vela_shadow_alpha', 'vela_shadow_blur', 'vela_shadow_offset_x', 'vela_shadow_offset_y'):
                    window.appearance_controls[key].editing_container.setEnabled(False)

    return simple_layout
