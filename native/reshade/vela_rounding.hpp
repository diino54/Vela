// Vela rounded outer docking corners. SPDX-License-Identifier: MIT
// Geometry-only clipping: no game-frame capture, render targets or API-specific
// shaders. Interpolate UV/color and feather the one-pixel boundary. Popups and
// OSD are excluded. Called after ImGui::Render, before GPU buffers are uploaded.
#pragma once
#include <imgui.h>
#include <imgui_internal.h>
#include <algorithm>
#include <cmath>
#include <vector>

namespace vela_rounding
{
// Keep requests in the owning ImGui window's storage, so runtime/context
// destruction requires no external state cleanup. Process before Begin calls.
inline void request_detach(ImGuiWindow &window)
{
    window.StateStorage.SetBool(ImHashStr("VelaDetachPanel",0,window.ID),true);
}
inline void process_detach_requests(ImGuiContext &ctx)
{
    for (ImGuiWindow *window:ctx.Windows)
    {
        const ImGuiID key=ImHashStr("VelaDetachPanel",0,window->ID);
        if (!window->StateStorage.GetBool(key)) continue;
        window->StateStorage.SetBool(key,false);
        ImGuiDockNode *node=window->DockNode;
        if (!node || !node->IsLeafNode() || (!node->ParentNode && !node->IsDockSpace())) continue;
        ImGui::DockContextProcessUndockNode(&ctx,node);
        node=window->DockNode; // Central/root nodes are replaced during undock.
        node->WantMouseMove=false;
        ImGuiViewport *viewport=window->Viewport;
        const ImVec2 size(std::min(node->Size.x,viewport->WorkSize.x-48),std::min(node->Size.y,viewport->WorkSize.y-48));
        ImGui::DockBuilderSetNodeSize(node->ID,ImVec2(std::max(160.f,size.x),std::max(120.f,size.y)));
        const ImVec2 position(viewport->WorkPos.x+24,viewport->WorkPos.y+24);
        ImGui::DockBuilderSetNodePos(node->ID,position);
        // A single-tab node may collapse to a plain floating window. Set its
        // window geometry too, so that path cannot restore the old dock size.
        for (ImGuiWindow *tab:node->Windows)
        {
            ImGui::SetWindowPos(tab,position,ImGuiCond_Always);
            ImGui::SetWindowSize(tab,node->Size,ImGuiCond_Always);
        }
        ImGui::FocusWindow(window);
        ImGui::MarkIniSettingsDirty();
        break;
    }
}
inline void panel_controls()
{
    ImGuiWindow *window=ImGui::GetCurrentWindow();
    ImGuiDockNode *node=window->DockNode;
    const bool attached=node && (node->ParentNode || node->IsDockSpace());
    if (attached)
    {
        if (ImGui::SmallButton("Detach panel")) request_detach(*window);
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("Detach this entire group of tabs from the screen edge.");
    }
    else
    {
        ImGui::SmallButton("Move panel");
        if (ImGui::IsItemActivated()) ImGui::StartMouseMovingWindowOrNode(window,node,false);
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("Drag here to move the panel. Drag a tab to dock it again.");
    }
    ImGui::Separator();
}

struct vertex { ImVec2 pos, uv; float color[4]; };
using polygon = std::vector<vertex>;
struct corner { float x, y, radius; int sx, sy; };
struct plane { float x, y, bound; };

inline vertex unpack(const ImDrawVert &v)
{
    const ImVec4 c = ImGui::ColorConvertU32ToFloat4(v.col);
    return {v.pos, v.uv, {c.x,c.y,c.z,c.w}};
}
inline vertex mix(const vertex &a, const vertex &b, float t)
{
    vertex v = a;
    v.pos = ImVec2(a.pos.x+(b.pos.x-a.pos.x)*t, a.pos.y+(b.pos.y-a.pos.y)*t);
    v.uv = ImVec2(a.uv.x+(b.uv.x-a.uv.x)*t, a.uv.y+(b.uv.y-a.uv.y)*t);
    for (int i=0; i<4; ++i) v.color[i] += (b.color[i]-a.color[i])*t;
    return v;
}
inline polygon clip(const polygon &input, plane p)
{
    polygon out;
    if (input.empty()) return out;
    vertex a = input.back(); float da = a.pos.x*p.x+a.pos.y*p.y-p.bound;
    for (const vertex &b : input)
    {
        const float db = b.pos.x*p.x+b.pos.y*p.y-p.bound;
        if ((da <= 0) != (db <= 0)) out.push_back(mix(a,b,da/(da-db)));
        if (db <= 0) out.push_back(b);
        a=b; da=db;
    }
    return out;
}
inline bool overlaps(const polygon &poly, const corner &c)
{
    const float left=c.x+(c.sx<0?-c.radius:0), top=c.y+(c.sy<0?-c.radius:0);
    float minx=poly[0].pos.x,maxx=minx,miny=poly[0].pos.y,maxy=miny;
    for (const auto &v:poly) { minx=std::min(minx,v.pos.x);maxx=std::max(maxx,v.pos.x);miny=std::min(miny,v.pos.y);maxy=std::max(maxy,v.pos.y); }
    return maxx>left && minx<left+c.radius && maxy>top && miny<top+c.radius;
}
inline void cut_corner(const polygon &input, const corner &c, std::vector<polygon> &output)
{
    if (!overlaps(input,c)) { output.push_back(input); return; }
    const float left=c.x+(c.sx<0?-c.radius:0), top=c.y+(c.sy<0?-c.radius:0);
    // Partition the triangle into disjoint pieces outside the corner square,
    // and the piece inside it. Never clip unrelated geometry across the screen.
    polygon inside=input;
    for (plane p : {plane{-1,0,-left},plane{1,0,left+c.radius},plane{0,-1,-top},plane{0,1,top+c.radius}})
    {
        polygon outside=clip(inside,{-p.x,-p.y,-p.bound});
        if (outside.size()>=3) output.push_back(std::move(outside));
        inside=clip(inside,p);
        if (inside.size()<3) return;
    }
    constexpr int segments=12;
    constexpr float pi=3.14159265358979323846f;
    std::vector<plane> planes;
    for (int i=0;i<segments;++i)
    {
        const float angle=(i+0.5f)*(pi*0.5f/segments);
        const float nx=c.sx*std::cos(angle),ny=c.sy*std::sin(angle);
        planes.push_back({nx,ny,nx*c.x+ny*c.y+c.radius*std::cos(pi*0.25f/segments)-0.5f});
    }
    // Core is fully opaque; disjoint edge strips carry a 1px alpha ramp.
    for (const plane &p:planes)
    {
        polygon fringe=clip(inside,{-p.x,-p.y,-p.bound});
        for (const plane &q:planes) fringe=clip(fringe,{q.x,q.y,q.bound+1});
        if (fringe.size()>=3)
        {
            for (vertex &v:fringe)
            {
                float coverage=1;
                for (const plane &q:planes) coverage=std::min(coverage,1-(v.pos.x*q.x+v.pos.y*q.y-q.bound));
                v.color[3]*=std::max(0.f,coverage);
            }
            output.push_back(std::move(fringe));
        }
        inside=clip(inside,p);
        if (inside.size()<3) return;
    }
    output.push_back(std::move(inside));
}
inline bool touches(const ImDrawVert *v, const ImDrawIdx *idx, const std::vector<corner> &corners)
{
    const float minx=std::min({v[idx[0]].pos.x,v[idx[1]].pos.x,v[idx[2]].pos.x});
    const float maxx=std::max({v[idx[0]].pos.x,v[idx[1]].pos.x,v[idx[2]].pos.x});
    const float miny=std::min({v[idx[0]].pos.y,v[idx[1]].pos.y,v[idx[2]].pos.y});
    const float maxy=std::max({v[idx[0]].pos.y,v[idx[1]].pos.y,v[idx[2]].pos.y});
    for (const auto &c:corners)
    {
        const float left=c.x+(c.sx<0?-c.radius:0),top=c.y+(c.sy<0?-c.radius:0);
        if (maxx>left && minx<left+c.radius && maxy>top && miny<top+c.radius) return true;
    }
    return false;
}
inline void apply(ImDrawList &list, const std::vector<corner> &corners)
{
    bool affected=false;
    for (const auto &cmd:list.CmdBuffer)
        if (!cmd.UserCallback)
            for (unsigned i=0;i+2<cmd.ElemCount;i+=3)
                if (touches(list.VtxBuffer.Data+cmd.VtxOffset,list.IdxBuffer.Data+cmd.IdxOffset+i,corners)) { affected=true;break; }
    if (!affected) return;
    ImVector<ImDrawVert> vertices; vertices=list.VtxBuffer;
    ImVector<ImDrawIdx> indices;
    ImVector<ImDrawCmd> commands;
    for (const auto &source:list.CmdBuffer)
    {
        ImDrawCmd run=source; run.IdxOffset=indices.Size; run.ElemCount=0;
        if (source.UserCallback) { commands.push_back(run);continue; }
        for (unsigned i=0;i+2<source.ElemCount;i+=3)
        {
            const ImDrawIdx *idx=list.IdxBuffer.Data+source.IdxOffset+i;
            const ImDrawVert *v=list.VtxBuffer.Data+source.VtxOffset;
            if (!touches(v,idx,corners))
            {
                for (int k=0;k<3;++k) indices.push_back(idx[k]);
                run.ElemCount+=3;continue;
            }
            if (run.ElemCount) commands.push_back(run);
            std::vector<polygon> pieces{{unpack(v[idx[0]]),unpack(v[idx[1]]),unpack(v[idx[2]])}};
            for (const corner &c:corners)
            {
                std::vector<polygon> next;
                for (const auto &piece:pieces) cut_corner(piece,c,next);
                pieces=std::move(next);
            }
            for (const polygon &piece:pieces)
            {
                if (piece.size()<3) continue;
                ImDrawCmd part=source;part.VtxOffset=vertices.Size;part.IdxOffset=indices.Size;part.ElemCount=0;
                for (const vertex &p:piece)
                    vertices.push_back({p.pos,p.uv,ImGui::ColorConvertFloat4ToU32(ImVec4(p.color[0],p.color[1],p.color[2],p.color[3]))});
                for (unsigned k=1;k+1<piece.size();++k) { indices.push_back(0);indices.push_back(static_cast<ImDrawIdx>(k));indices.push_back(static_cast<ImDrawIdx>(k+1));part.ElemCount+=3; }
                commands.push_back(part);
            }
            run=source;run.IdxOffset=indices.Size;run.ElemCount=0;
        }
        if (run.ElemCount) commands.push_back(run);
    }
    list.VtxBuffer.swap(vertices);list.IdxBuffer.swap(indices);list.CmdBuffer.swap(commands);
}
inline void apply(ImGuiContext &ctx, ImDrawData &data, float radius)
{
    if (radius<=0) return;
    std::vector<ImRect> bounds;
    std::vector<ImDrawList *> lists;
    for (ImGuiWindow *window:ctx.Windows)
    {
        if (!window->Active || window->Hidden || (window->Flags & ImGuiWindowFlags_Popup)) continue;
        ImGuiWindow *root=window->RootWindow;
        if (root->DockIsActive && root->DockNode)
        {
            ImGuiDockNode *node=root->DockNode;
            ImRect rect(node->Pos,ImVec2(node->Pos.x+node->Size.x,node->Pos.y+node->Size.y));
            bool found=false;
            for (const auto &other:bounds) if (other.Min.x==rect.Min.x && other.Min.y==rect.Min.y && other.Max.x==rect.Max.x && other.Max.y==rect.Max.y) found=true;
            if (!found) bounds.push_back(rect);
            lists.push_back(window->DrawList);
            if (node->HostWindow) lists.push_back(node->HostWindow->DrawList);
        }
    }
    // Adjacent rectangular panes form one outer surface. Internal split edges
    // stay straight and retain the original docking hit regions.
    for (size_t i=0;i<bounds.size();++i)
        for (size_t j=i+1;j<bounds.size();)
        {
            const auto &a=bounds[i];const auto &b=bounds[j];
            const bool horizontal=std::abs(a.Min.y-b.Min.y)<1 && std::abs(a.Max.y-b.Max.y)<1 && (std::abs(a.Max.x-b.Min.x)<8 || std::abs(b.Max.x-a.Min.x)<8);
            const bool vertical=std::abs(a.Min.x-b.Min.x)<1 && std::abs(a.Max.x-b.Max.x)<1 && (std::abs(a.Max.y-b.Min.y)<8 || std::abs(b.Max.y-a.Min.y)<8);
            if (horizontal || vertical) { bounds[i].Add(b);bounds.erase(bounds.begin()+j);i=static_cast<size_t>(-1);break; } else ++j;
        }
    std::vector<corner> corners;
    for (const auto &rect:bounds)
    {
        const float r=std::min(radius,std::min(rect.GetWidth(),rect.GetHeight())*.5f);
        corners.push_back({rect.Min.x+r,rect.Min.y+r,r,-1,-1});
        corners.push_back({rect.Max.x-r,rect.Min.y+r,r,1,-1});
        corners.push_back({rect.Min.x+r,rect.Max.y-r,r,-1,1});
        corners.push_back({rect.Max.x-r,rect.Max.y-r,r,1,1});
    }
    data.TotalVtxCount=data.TotalIdxCount=0;
    for (ImDrawList *list:data.CmdLists)
    {
        if (std::find(lists.begin(),lists.end(),list)!=lists.end()) vela_rounding::apply(*list,corners);
        data.TotalVtxCount+=list->VtxBuffer.Size;data.TotalIdxCount+=list->IdxBuffer.Size;
    }
}
}
