Texture2D t0 : register(t0);
SamplerState s0 : register(s0);

cbuffer PushConstants : register(b0)
{
	// Offset from the orthographic projection matrix used in the vertex shader
	uint color_space : packoffset(c4.x);
	float hdr_overlay_brightness : packoffset(c4.y);
    float2 vela_texel : packoffset(c4.z);
    float vela_radius : packoffset(c5.x);
    float vela_quality : packoffset(c5.y);
    float vela_enabled : packoffset(c5.z);
    uint vela_color_space : packoffset(c5.w);
};

#include "imgui_hdr.hlsl"

// Decode each original texel before any interpolation/filtering in HDR.
float4 vela_fetch(float2 uv) {
    int2 size = int2(round(1.0 / vela_texel));
    int2 pixel = clamp(int2(floor(uv * float2(size))), int2(0,0), size-int2(1,1));
    return t0.Load(int3(pixel,0));
}
#define VELA_SAMPLE(uv) vela_fetch(uv)

// @VELA_BLUR_FUNCTIONS@

void main(float4 vpos : SV_POSITION, float4 vcol : COLOR0, float2 uv : TEXCOORD0, out float4 col : SV_TARGET)
{
    if (vela_enabled > .5) { col=vela_blur(uv,vcol.a); return; }
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

	col = t0.Sample(s0, uv);
	col *= vcol; // Blend vertex color and texture
}
