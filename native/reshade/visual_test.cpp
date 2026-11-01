#include "vela_visual.hpp"
#include <cassert>
#include <iostream>
int main() {
    vela_visual::transition motion;
    float previous=0;
    for(int i=0;i<30;++i){float value=motion.update(true,1.f/60,true,.24f);assert(value>=previous);previous=value;}
    assert(motion.value==1.f);
    for(int i=0;i<30;++i){float value=motion.update(false,1.f/60,true,.24f);assert(value<=previous);previous=value;}
    assert(motion.value==0.f);
    motion.update(true,.05f,true,.24f);float midway=motion.value;motion.update(false,.01f,true,.24f);assert(motion.value<midway);
    assert(motion.update(true,0,false,.24f)==1);assert(motion.update(false,0,false,.24f)==0);
    auto *ctx=ImGui::CreateContext();auto &io=ImGui::GetIO();io.IniFilename=nullptr;io.DisplaySize=ImVec2(960,640);io.DeltaTime=1.f/60;io.ConfigFlags|=ImGuiConfigFlags_DockingEnable;
    unsigned char *pixels;int w,h;io.Fonts->GetTexDataAsRGBA32(&pixels,&w,&h);io.Fonts->SetTexID(1);
    for(int frame=0;frame<4;++frame){
        ImGui::NewFrame();ImGui::SetNextWindowPos(ImVec2(0,0));ImGui::SetNextWindowSize(io.DisplaySize);
        ImGui::Begin("Viewport",nullptr,ImGuiWindowFlags_NoBackground|ImGuiWindowFlags_NoDecoration|ImGuiWindowFlags_NoDocking);
        auto id=ImGui::GetID("Dock");
        if(frame==0){ImGui::DockBuilderAddNode(id,ImGuiDockNodeFlags_DockSpace);ImGui::DockBuilderSetNodePos(id,ImVec2(30,80));ImGui::DockBuilderSetNodeSize(id,ImVec2(300,520));ImGui::DockBuilderDockWindow("Home",id);ImGui::DockBuilderFinish(id);}
        ImGui::SetCursorScreenPos(ImVec2(30,80));ImGui::DockSpace(id,ImVec2(300,520));ImGui::End();
        ImGui::Begin("Home");ImGui::TextUnformatted("Vela");ImGui::End();
        // Before Render, the implicit fallback is still Active; never blur it.
        auto rectangles=vela_visual::surfaces(*ctx);
        std::cout<<"frame "<<frame<<" surfaces "<<rectangles.size()<<"\n";
        if(frame>=2){assert(rectangles.size()==1);assert(rectangles[0].Min.x==30&&rectangles[0].Min.y==80&&rectangles[0].GetWidth()==300);}
        const float original_alpha=ImGui::GetStyle().Alpha;ImGui::Render();
        vela_visual::animate(*ctx,.5f,true);assert(ImGui::GetStyle().Alpha==original_alpha);
    }
    ImGui::DestroyContext();std::cout<<"PASS: reversible fades, disabled animation, dock-only backdrop bounds and persistent style alpha\n";
}
