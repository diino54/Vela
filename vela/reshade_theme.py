"""Vela's optional ReShade UI preset, using upstream 6.8 STYLE/OVERLAY keys.

ReShade's ImGui renderer consumes RGBA floats and its own font-size units.
This mirrors Vela's palette and rounded controls, not Qt's frosted material.
"""


def rgba(hex_color, alpha=1):
    return (
        ",".join(f"{int(hex_color[index : index + 2], 16) / 255:.6f}" for index in (1, 3, 5))
        + f",{alpha:.6f}"
    )


def vela_theme():
    colors = {}

    def group(names, color, alpha=1):
        for name in names.split():
            colors[name] = rgba(color, alpha)

    group("Text", "#ffffff")
    group("TextDisabled", "#b8b8b8")
    group("WindowBg PopupBg", "#181818")
    group("ChildBg", "#202020")
    group("Border Separator", "#303030")
    group("BorderShadow", "#000000", 0)
    group("FrameBg", "#111111")
    group("FrameBgHovered", "#181818")
    group("FrameBgActive", "#242424")
    group("TitleBg TitleBgCollapsed", "#181818")
    group("TitleBgActive MenuBarBg", "#202020")
    group("ScrollbarBg", "#0f0f0f")
    group("ScrollbarGrab", "#444444")
    group("ScrollbarGrabHovered", "#555555")
    group("ScrollbarGrabActive", "#686868")
    group("Button Header Tab TabDimmed", "#303030")
    group("ButtonHovered HeaderHovered TabHovered", "#404040")
    group("ButtonActive HeaderActive TabSelected TabDimmedSelected", "#353535")
    group(
        "CheckMark SliderGrab SliderGrabActive SeparatorHovered SeparatorActive ResizeGripHovered ResizeGripActive TabSelectedOverline TabDimmedSelectedOverline PlotLinesHovered PlotHistogram PlotHistogramHovered NavCursor NavHighlight DockingPreview",
        "#246bce",
    )
    group("ResizeGrip", "#444444", 0.5)
    group("TextSelectedBg", "#246bce", 0.5)
    group("DockingEmptyBg", "#111111")
    group("PlotLines", "#999999")
    group("DragDropTarget", "#347cde")
    group("NavWindowingHighlight", "#dddddd", 0.7)
    group("NavWindowingDimBg ModalWindowDimBg", "#000000", 0.65)
    style = {
        "StyleIndex": "4",
        "EditorStyleIndex": "0",
        "FontSize": "13",
        "EditorFontSize": "13",
        "FontScale": "1",
        "Alpha": "0.7",
        "HdrOverlayBrightness": "400",
    }
    style.update(
        {key: "7" for key in ("FrameRounding", "GrabRounding", "ScrollbarRounding", "TabRounding")}
    )
    style.update({key: "12" for key in ("WindowRounding", "ChildRounding", "PopupRounding")})
    style.update(colors)
    return "\n[OVERLAY]\nShowFPS=0\n\n[STYLE]\n" + "".join(
        f"{key}={value}\n" for key, value in style.items()
    )
