#include "vela_font_scale.hpp"
#include <cassert>
#include <iostream>
int main()
{
    using vela_font_scale::on_resource_init;
    // Explicit 13px + scale 1 must not turn into 1.5/2 during creation/reset.
    assert(on_resource_init(1,13,2160,true,0)==1);
    assert(on_resource_init(1,13,1440,true,120)==1);
    // Automatic initial sizing remains available, then survives res changes.
    float scale=on_resource_init(1,13,1440,false,0);assert(scale==1.5f);
    for (unsigned height:{1080u,2160u,720u,1440u,2160u})
        assert(on_resource_init(scale,13,height,false,200)==1.5f);
    // Font 10 and intentional custom zoom must remain unchanged as well.
    assert(on_resource_init(1,10,2160,true,100)==1);
    assert(on_resource_init(1.25f,10,1080,true,500)==1.25f);
    // Legacy zero-scale configuration falls back without producing zero fonts.
    assert(on_resource_init(0,13,1440,false,0)==1.5f);
    std::cout<<"PASS: explicit and automatic font scales survive resource resets; custom size/zoom and legacy defaults preserved\n";
}
