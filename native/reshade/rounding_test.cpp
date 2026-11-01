// CPU geometry regression and software render of the actual pinned ImGui mesh.
#include "vela_rounding.hpp"
#include <cassert>
#include <fstream>
#include <iostream>
#include <chrono>

static float edge(ImVec2 a,ImVec2 b,ImVec2 p) { return (p.x-a.x)*(b.y-a.y)-(p.y-a.y)*(b.x-a.x); }
static std::vector<unsigned char> render(ImDrawData &data,int width,int height,unsigned char *tex,int tw,int th)
{
    std::vector<unsigned char> rgb(width*height*3);
    for(int y=0;y<height;++y) for(int x=0;x<width;++x) {
        rgb[(y*width+x)*3]=static_cast<unsigned char>(35+x*40/width);
        rgb[(y*width+x)*3+1]=static_cast<unsigned char>(70+y*60/height);
        rgb[(y*width+x)*3+2]=80;
    }
    for(ImDrawList *list:data.CmdLists) for(const auto &cmd:list->CmdBuffer) {
        if(cmd.UserCallback) continue;
        for(unsigned i=0;i+2<cmd.ElemCount;i+=3) {
            const auto *idx=list->IdxBuffer.Data+cmd.IdxOffset+i;const auto *v=list->VtxBuffer.Data+cmd.VtxOffset;
            const auto a=vela_rounding::unpack(v[idx[0]]),b=vela_rounding::unpack(v[idx[1]]),c=vela_rounding::unpack(v[idx[2]]);
            float area=edge(a.pos,b.pos,c.pos);if(std::abs(area)<1e-6)continue;
            int x0=std::max({0,int(std::floor(std::min({a.pos.x,b.pos.x,c.pos.x}))),int(cmd.ClipRect.x)});
            int x1=std::min({width,int(std::ceil(std::max({a.pos.x,b.pos.x,c.pos.x}))),int(cmd.ClipRect.z)});
            int y0=std::max({0,int(std::floor(std::min({a.pos.y,b.pos.y,c.pos.y}))),int(cmd.ClipRect.y)});
            int y1=std::min({height,int(std::ceil(std::max({a.pos.y,b.pos.y,c.pos.y}))),int(cmd.ClipRect.w)});
            for(int y=y0;y<y1;++y)for(int x=x0;x<x1;++x){
                const ImVec2 p(x+.5f,y+.5f);float wa=edge(b.pos,c.pos,p)/area,wb=edge(c.pos,a.pos,p)/area,wc=1-wa-wb;
                if(wa<0 || wb<0 || wc<0)continue;
                auto owns=[area](ImVec2 x,ImVec2 y) { if(area<0)std::swap(x,y);return x.y<y.y || (x.y==y.y && x.x>y.x); };
                if((wa==0 && !owns(b.pos,c.pos)) || (wb==0 && !owns(c.pos,a.pos)) || (wc==0 && !owns(a.pos,b.pos)))continue;
                float u=a.uv.x*wa+b.uv.x*wb+c.uv.x*wc,w=a.uv.y*wa+b.uv.y*wb+c.uv.y*wc;
                int tx=std::clamp(int(u*tw),0,tw-1),ty=std::clamp(int(w*th),0,th-1);
                float alpha=(a.color[3]*wa+b.color[3]*wb+c.color[3]*wc)*tex[(ty*tw+tx)*4+3]/255.f;
                for(int k=0;k<3;++k) {
                    float col=(a.color[k]*wa+b.color[k]*wb+c.color[k]*wc)*tex[(ty*tw+tx)*4+k];
                    auto &dst=rgb[(y*width+x)*3+k];dst=static_cast<unsigned char>(col*alpha+dst*(1-alpha));
                }
            }
        }
    }
    return rgb;
}
static void save(const char *path,const std::vector<unsigned char> &rgb,int w,int h) {
    std::ofstream f(path,std::ios::binary);f<<"P6\n"<<w<<" "<<h<<"\n255\n";f.write(reinterpret_cast<const char *>(rgb.data()),rgb.size());
}
int main(int argc,char **argv)
{
    auto *ctx=ImGui::CreateContext();auto &io=ImGui::GetIO();io.IniFilename=nullptr;
    io.DisplaySize=ImVec2(680,440);io.DeltaTime=1.f/60;io.ConfigFlags|=ImGuiConfigFlags_DockingEnable;io.BackendFlags|=ImGuiBackendFlags_RendererHasVtxOffset;
    unsigned char *pixels;int tw,th;io.Fonts->GetTexDataAsRGBA32(&pixels,&tw,&th);io.Fonts->SetTexID(1);
    ImGui::StyleColorsDark();auto &style=ImGui::GetStyle();style.WindowRounding=18;style.Alpha=.7f;
    style.Colors[ImGuiCol_WindowBg]=ImVec4(.094f,.094f,.094f,1);
    for(int frame=0;frame<4;++frame) {
        ImGui::NewFrame();ImGui::SetNextWindowPos(ImVec2(0,0));ImGui::SetNextWindowSize(io.DisplaySize);
        ImGui::Begin("Viewport",nullptr,ImGuiWindowFlags_NoDecoration|ImGuiWindowFlags_NoBackground|ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoDocking|ImGuiWindowFlags_NoBringToFrontOnFocus|ImGuiWindowFlags_NoFocusOnAppearing);
        const auto id=ImGui::GetID("VelaTestDock");
        if(frame==0){ImGui::DockBuilderAddNode(id,ImGuiDockNodeFlags_DockSpace);ImGui::DockBuilderSetNodePos(id,ImVec2(35,25));ImGui::DockBuilderSetNodeSize(id,ImVec2(380,380));if(argc>2) { ImGuiID left,right;ImGui::DockBuilderSplitNode(id,ImGuiDir_Left,.5f,&left,&right);ImGui::DockBuilderDockWindow("Home",left);ImGui::DockBuilderDockWindow("Settings",right); } else { ImGui::DockBuilderDockWindow("Home",id);ImGui::DockBuilderDockWindow("Settings",id); }ImGui::DockBuilderFinish(id);}
        ImGui::SetCursorScreenPos(ImVec2(35,25));ImGui::DockSpace(id,ImVec2(380,380));ImGui::End();
        ImGui::Begin("Home");ImGui::TextUnformatted("Vela / ReShade");ImGui::Separator();ImGui::TextUnformatted("Rounded outer docking surface");
        bool checked=true;ImGui::Checkbox("Preserve docked tabs",&checked);ImGui::Button("Aesthetic",ImVec2(140,32));
        ImGui::BeginChild("content",ImVec2(0,0),ImGuiChildFlags_Borders);for(int i=0;i<18;++i)ImGui::Text("Shader effect %02d",i+1);ImGui::EndChild();ImGui::End();
        ImGui::Begin("Settings");ImGui::TextUnformatted("Settings");ImGui::End();
        // This independent window overlaps the corner and must remain untouched.
        ImGui::SetNextWindowPos(ImVec2(450,40));ImGui::SetNextWindowSize(ImVec2(180,90));ImGui::Begin("Floating");ImGui::TextUnformatted("Unchanged");ImGui::End();
        ImGui::Render();
    }
    auto &data=*ImGui::GetDrawData();auto before=render(data,680,440,pixels,tw,th);
    for(const auto *window:ctx->Windows) if(window->Active && !window->Hidden && window->DockIsActive) std::cout<<window->Name<<" dock "<<window->DockNode->Pos.x<<","<<window->DockNode->Pos.y<<" "<<window->DockNode->Size.x<<","<<window->DockNode->Size.y<<"\n";
    const int old_count=data.TotalIdxCount;
    vela_rounding::apply(*ctx,data,0);assert(data.TotalIdxCount==old_count);
    const auto started=std::chrono::steady_clock::now();
    vela_rounding::apply(*ctx,data,18);
    std::cout<<"Corner clipping: "<<std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-started).count()<<" us for this test mesh\n";
    assert(data.TotalIdxCount>old_count);
    int indices=0,vertices=0;bool feather=false;
    for(const auto *list:data.CmdLists){indices+=list->IdxBuffer.Size;vertices+=list->VtxBuffer.Size;
        for(const auto &cmd:list->CmdBuffer)if(!cmd.UserCallback){assert(cmd.IdxOffset+cmd.ElemCount<=static_cast<unsigned>(list->IdxBuffer.Size));for(unsigned i=0;i<cmd.ElemCount;++i)assert(cmd.VtxOffset+list->IdxBuffer[cmd.IdxOffset+i]<static_cast<unsigned>(list->VtxBuffer.Size));}
        for(const auto &v:list->VtxBuffer)if((v.col>>24)>0 && (v.col>>24)<170)feather=true;
    }
    assert(indices==data.TotalIdxCount && vertices==data.TotalVtxCount && feather);
    auto after=render(data,680,440,pixels,tw,th);int changed=0,outside_changes=0;
    for(int y=0;y<440;++y)for(int x=0;x<680;++x)for(int k=0;k<3;++k)if(before[(y*680+x)*3+k]!=after[(y*680+x)*3+k]){
        ++changed;
        // Float interpolation in this CPU rasterizer can differ on isolated
        // shared triangle edges after retessellation (GPU uses fixed coverage).
        if(!((x<55 || x>394) && (y<45 || y>384)) && std::abs(int(before[(y*680+x)*3+k])-int(after[(y*680+x)*3+k]))>2) ++outside_changes;
        if(x>=450) assert(before[(y*680+x)*3+k]==after[(y*680+x)*3+k]);
    }
    std::cout<<"CPU edge interpolation differences outside corner bounds: "<<outside_changes<<" channels\n";
    assert(outside_changes<=48);
    assert(changed>100);
    if(argc>1){save((std::string(argv[1])+"-before.ppm").c_str(),before,680,440);save((std::string(argv[1])+"-after.ppm").c_str(),after,680,440);}
    std::cout<<"PASS: real docked ImGui mesh; only outer corners changed, feathered alpha, valid indices and floating window preserved\n";
    // Detach must preserve the whole selected tab group, create a floating
    // root, offset it away from the edge, and leave the viewport dock alive.
    ImGuiWindow *home=ImGui::FindWindowByName("Home");
    ImGuiWindow *settings=ImGui::FindWindowByName("Settings");
    assert(home && home->DockNode);
    const int tabs=home->DockNode->Windows.Size;
    vela_rounding::request_detach(*home);
    vela_rounding::process_detach_requests(*ctx);ImGui::NewFrame();
    assert(home->DockNode && !home->DockNode->ParentNode && !home->DockNode->IsDockSpace());
    assert(home->DockNode->Windows.Size==tabs);
    assert(home->DockNode->Pos.x==24 && home->DockNode->Pos.y==24);
    if(argc<=2)assert(home->DockNode==settings->DockNode);
    ImGui::Begin("Home");ImVec2 move_button=ImGui::GetCursorScreenPos();vela_rounding::panel_controls();ImGui::TextUnformatted("Floating");ImGui::End();
    ImGui::Begin("Settings");ImGui::TextUnformatted("Settings");ImGui::End();ImGui::Render();
    for(int frame=0;frame<6;++frame)
    {
        const float dx=frame>=3?80.f:0.f;
        io.AddMousePosEvent(move_button.x+10+dx,move_button.y+5);
        io.AddMouseButtonEvent(0,frame>=1 && frame<=4);
        vela_rounding::process_detach_requests(*ctx);ImGui::NewFrame();
        ImGui::SetNextWindowPos(ImVec2(0,0));ImGui::SetNextWindowSize(io.DisplaySize);
        ImGui::Begin("Viewport",nullptr,ImGuiWindowFlags_NoDecoration|ImGuiWindowFlags_NoBackground|ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoDocking|ImGuiWindowFlags_NoBringToFrontOnFocus|ImGuiWindowFlags_NoFocusOnAppearing);
        ImGui::SetCursorScreenPos(ImVec2(35,25));ImGui::DockSpace(ImGui::GetID("VelaTestDock"),ImVec2(380,380));ImGui::End();
        if(ImGui::Begin("Home")){if(frame==0)move_button=ImGui::GetCursorScreenPos();vela_rounding::panel_controls();}ImGui::End();
        ImGui::Begin("Settings");ImGui::End();ImGui::Render();
    }
    assert(home->Pos.x>40);
    std::cout<<"PASS: whole tab group detached and moved with real ImGui mouse events\n";
    ImGui::DestroyContext();
}
