#version 430

layout(location = 0) in vec2 pos;
layout(location = 1) in vec2 tex;
layout(location = 2) in vec4 col;

out vec4 frag_col;
out vec2 frag_tex;

layout(binding = 0, std140) uniform PushConstants
{
    mat4 ortho_projection;
    uint color_space;
    float hdr_overlay_brightness;
    vec2 vela_texel;
    float vela_radius;
    float vela_quality;
    float vela_enabled;
    uint vela_color_space;
};

void main()
{
	frag_col = col;
	frag_tex = tex;
	gl_Position = ortho_projection * vec4(pos.xy, 0, 1);
}
