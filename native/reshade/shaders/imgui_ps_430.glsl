#version 430

layout(binding = 0) uniform sampler2D s0;

in vec4 frag_col;
in vec2 frag_tex;

out vec4 col;

layout(binding = 0, std140) uniform PushConstants {
    mat4 ortho_projection;
    uint color_space;
    float hdr_overlay_brightness;
    vec2 vela_texel;
    float vela_radius;
    float vela_quality;
    float vela_enabled;
    uint vela_color_space;
};
vec4 vela_fetch(vec2 uv) {
    ivec2 size = ivec2(round(1.0 / vela_texel));
    ivec2 pixel = clamp(ivec2(floor(uv * vec2(size))), ivec2(0), size-ivec2(1));
    return texelFetch(s0,pixel,0);
}
#define VELA_SAMPLE(uv) vela_fetch(uv)

// @VELA_BLUR_FUNCTIONS@

void main()
{
    if (vela_enabled > .5) { col=vela_blur(frag_tex,frag_col.a); return; }
	col = texture(s0, frag_tex);
	col *= frag_col; // Blend vertex color and texture
}
