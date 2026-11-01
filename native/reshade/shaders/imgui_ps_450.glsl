#version 450 core
#extension GL_ARB_shading_language_include : require

layout(set = 0, binding = 0) uniform sampler2D s0;

layout(location = 0) in struct { vec4 col; vec2 tex; } i;
vec4 vcol = i.col;
layout(location = 0) out vec4 col;

layout(push_constant) uniform PushConstants
{
	// Offset from the orthographic projection matrix used in the vertex shader
	layout(offset = 64) uint color_space;
	layout(offset = 68) float hdr_overlay_brightness;
    layout(offset = 72) vec2 vela_texel;
    layout(offset = 80) float vela_radius;
    layout(offset = 84) float vela_quality;
    layout(offset = 88) float vela_enabled;
    layout(offset = 92) uint vela_color_space;
};

#include "imgui_hdr.hlsl"

vec4 vela_fetch(vec2 uv) {
    ivec2 size = ivec2(round(1.0 / vela_texel));
    ivec2 pixel = clamp(ivec2(floor(uv * vec2(size))), ivec2(0), size-ivec2(1));
    return texelFetch(s0,pixel,0);
}
#define VELA_SAMPLE(uv) vela_fetch(uv)

// @VELA_BLUR_FUNCTIONS@

void main()
{
    if (vela_enabled > .5) { col=vela_blur(i.tex,vcol.a); return; }
	switch (color_space)
	{
	case COLOR_SPACE_SCRGB:
		vcol.rgb = to_scrgb(vcol.rgb);
		break;
	case COLOR_SPACE_HDR10_PQ:
		vcol.rgb = to_hdr10_pq(vcol.rgb);
		break;
	case COLOR_SPACE_HDR10_HLG:
		vcol.rgb = to_hdr10_hlg(vcol.rgb);
		break;
	}

	col = texture(s0, i.tex);
	col *= vcol; // Blend vertex color and texture
}
