// Linear-light Gaussian backdrop blur, including PQ, HLG and scRGB.

float3 vela_decode(float3 c) {
    if (vela_color_space == 2) return c; // scRGB is already linear.
    c = max(c, float3(0,0,0));
    if (vela_color_space == 3) {
        float3 p = pow(c, float3(1.0/78.84375,1.0/78.84375,1.0/78.84375));
        return pow(max(p-float3(.8359375,.8359375,.8359375),float3(0,0,0)) / max(float3(18.8515625,18.8515625,18.8515625)-18.6875*p,float3(.000001,.000001,.000001)), float3(1.0/.1593017578125,1.0/.1593017578125,1.0/.1593017578125));
    }
    if (vela_color_space == 4) {
        float3 hi = (exp((c-float3(.5599107146,.5599107146,.5599107146))/.17883277)+float3(.28466892,.28466892,.28466892))/12.0;
        return float3(c.r<=.5?c.r*c.r/3.0:hi.r,c.g<=.5?c.g*c.g/3.0:hi.g,c.b<=.5?c.b*c.b/3.0:hi.b);
    }
    float3 hi = pow((c+float3(.055,.055,.055))/1.055,float3(2.4,2.4,2.4));
    return float3(c.r<=.04045?c.r/12.92:hi.r,c.g<=.04045?c.g/12.92:hi.g,c.b<=.04045?c.b/12.92:hi.b);
}
float3 vela_encode(float3 c) {
    if (vela_color_space == 2) return c;
    c = max(c,float3(0,0,0));
    if (vela_color_space == 3) {
        float3 p = pow(c,float3(.1593017578125,.1593017578125,.1593017578125));
        return pow((float3(.8359375,.8359375,.8359375)+18.8515625*p)/(float3(1,1,1)+18.6875*p),float3(78.84375,78.84375,78.84375));
    }
    if (vela_color_space == 4) {
        float3 hi = .17883277*log(max(12.0*c-float3(.28466892,.28466892,.28466892),float3(.000001,.000001,.000001)))+float3(.5599107146,.5599107146,.5599107146);
        return float3(c.r<=1.0/12.0?sqrt(3.0*c.r):hi.r,c.g<=1.0/12.0?sqrt(3.0*c.g):hi.g,c.b<=1.0/12.0?sqrt(3.0*c.b):hi.b);
    }
    float3 hi = 1.055*pow(c,float3(1.0/2.4,1.0/2.4,1.0/2.4))-float3(.055,.055,.055);
    return float3(c.r<=.0031308?12.92*c.r:hi.r,c.g<=.0031308?12.92*c.g:hi.g,c.b<=.0031308?12.92*c.b:hi.b);
}
float4 vela_blur(float2 uv, float alpha) {
    int n = vela_quality < .5 ? 1 : vela_quality < 1.5 ? 2 : 3;
    float3 sum = float3(0,0,0); float weights = 0;
    for (int y=-3; y<=3; ++y) for (int x=-3; x<=3; ++x) {
        if (abs(x)>n || abs(y)>n) continue;
        float weight = exp(-float(x*x+y*y)/(float(n*n)*.65));
        float2 offset = float2(float(x),float(y)) * (vela_radius/float(n)) * vela_texel;
        sum += vela_decode(VELA_SAMPLE(uv+offset).rgb)*weight;
        weights += weight;
    }
    return float4(vela_encode(sum/weights),alpha);
}
