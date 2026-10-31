#include <cassert>
#include <memory>
#include "src/vela_color_state.h"
struct Params { int transfer=0; int color=42; };
int main() {
    using Snapshot=std::shared_ptr<Params>;
    VelaColorState<Snapshot> state;
    auto config=std::make_shared<Params>();
    int pq_context=1, sdr_context=2, applied_color=0, applied_transfer=-1, calls=0;
    auto draw=[&](const void* ctx, int transfer, bool dirty=false) {
        state.sync(ctx, config, dirty, [&](Params& local) {
            ++calls; local.transfer=transfer;
            applied_transfer=local.transfer; applied_color=local.color;
        });
    };
    draw(&pq_context,1); assert(applied_transfer==1 && applied_color==42);
    draw(&pq_context,1); assert(calls==1);
    // Another swapchain may briefly select SDR during an Alt-Tab.
    draw(&sdr_context,0); assert(applied_transfer==0);
    draw(&pq_context,1); assert(applied_transfer==1);
    // Reloaded settings are a new immutable snapshot with default transfer=0.
    config=std::make_shared<Params>();config->color=99;
    draw(&pq_context,1);assert(applied_transfer==1 && applied_color==99);
    assert(config->transfer==0); // Never publish a surface-dependent transform.
    int before=calls;draw(&pq_context,1,true);assert(calls==before+1);
    draw(&sdr_context,0);draw(&pq_context,1);assert(applied_color==99 && applied_transfer==1);
}
