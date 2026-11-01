// Vela ReShade font scale lifecycle. SPDX-License-Identifier: MIT
#pragma once
#include <cmath>

namespace vela_font_scale
{
// Resolution-based defaults are chosen only before the first GUI frame.
// Swapchain recreation (focus changes, resize, HDR transitions) must not replace
// an explicit or already resolved scale while FontSize still reports the same.
inline float on_resource_init(float current, float font_size, unsigned height, bool explicit_scale, int frame_count)
{
    const bool valid=std::isfinite(current) && current>0;
    if (valid && (explicit_scale || frame_count>0)) return current;
    if (font_size==13.f) return height>=2160?2.f:height>=1440?1.5f:1.f;
    return valid?current:1.f;
}
}
