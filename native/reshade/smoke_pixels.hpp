#pragma once
#include <cstdio>
#include <cmath>
#include <cstdint>
static float from_half(uint16_t bits) {
    const float sign = bits & 0x8000 ? -1.f : 1.f;
    const unsigned exponent = (bits >> 10) & 31, mantissa = bits & 1023;
    return exponent == 0 ? sign * std::ldexp(static_cast<float>(mantissa),-24) :
        exponent == 31 ? (mantissa ? NAN : sign*INFINITY) : sign*std::ldexp(1.f+mantissa/1024.f,static_cast<int>(exponent)-15);
}
static float pq_encode(float value) {
    const float p=std::pow(value,.1593017578125f);
    return std::pow((.8359375f+18.8515625f*p)/(1.f+18.6875f*p),78.84375f);
}
static float pq_decode(float value) {
    const float p=std::pow(value,1.f/78.84375f);
    return std::pow(std::fmax(p-.8359375f,0.f)/std::fmax(18.8515625f-18.6875f*p,.000001f),1.f/.1593017578125f);
}
static void save_pixels(const char *name,const void *data,UINT pitch,UINT width,UINT height,int hdr) {
            char path[128];std::snprintf(path,sizeof(path),"%s.partial.ppm",name);FILE *f=std::fopen(path,"wb");
            std::snprintf(path,sizeof(path),"%s.partial.rgb32f",name);FILE *raw=std::fopen(path,"wb");
            if(f)std::fprintf(f,"P6\n%u %u\n255\n",width,height);
            if(raw)std::fprintf(raw,"%u %u\n",width,height);
            for(UINT y=0;y<height;++y)for(UINT x=0;x<width;++x) {
                float rgb[3];unsigned char display[3];auto *row=static_cast<const unsigned char *>(data)+y*pitch;
                for(unsigned c=0;c<3;++c) {
                    rgb[c]=hdr==1?from_half(reinterpret_cast<const uint16_t *>(row)[x*4+c]):hdr==2?float((reinterpret_cast<const uint32_t *>(row)[x]>>(c*10))&1023)/1023.f:row[x*4+c]/255.f;
                    float value=rgb[c];if(hdr==1)value=value/(1.f+value);if(hdr==2){value=pq_decode(value)*10000.f/80.f;value=value/(1.f+value);}if(hdr)value=std::pow(std::fmax(value,0.f),1.f/2.2f);
                    display[c]=static_cast<unsigned char>(std::fmin(std::fmax(value,0.f),1.f)*255.f);
                }
                if(f)std::fwrite(display,1,3,f);if(raw)std::fwrite(rgb,sizeof(float),3,raw);
            }
            if(f)std::fclose(f);if(raw)std::fclose(raw);
            char final_path[128];
            std::snprintf(path,sizeof(path),"%s.partial.ppm",name);std::snprintf(final_path,sizeof(final_path),"%s.ppm",name);std::remove(final_path);std::rename(path,final_path);
            std::snprintf(path,sizeof(path),"%s.partial.rgb32f",name);std::snprintf(final_path,sizeof(final_path),"%s.rgb32f",name);std::remove(final_path);std::rename(path,final_path);
}
