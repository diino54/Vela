// Vela ReShade visual state. No layout transforms or game-image CPU readback.
#pragma once
#include "imgui_internal.h"
#include <algorithm>
#include <cmath>
#include <vector>

namespace vela_visual {
struct transition {
    float value = 0.0f;
    float update(bool open, float delta, bool enabled, float duration) {
        if (!enabled) return value = open ? 1.0f : 0.0f;
        const float step = std::clamp(delta, 0.0f, 0.1f) / std::clamp(duration, .08f, .8f);
        value = std::clamp(value + (open ? step : -step), 0.0f, 1.0f);
        return value * value * (3.0f - 2.0f * value);
    }
};
inline void animate(ImGuiContext &ctx, float opacity, bool enabled) {
    std::vector<ImDrawList *> visited;
    for (ImGuiWindow *window : ctx.Windows) {
        if (!window->Active || window->Hidden || window->IsFallbackWindow) continue;
        ImGuiWindow *root = window->RootWindow;
        if ((root->Flags & ImGuiWindowFlags_Tooltip) || ((root->Flags & ImGuiWindowFlags_NoDocking) && !root->DockIsActive && !(root->Flags & ImGuiWindowFlags_DockNodeHost))) continue;
        if (std::find(visited.begin(), visited.end(), window->DrawList) != visited.end()) continue;
        visited.push_back(window->DrawList);
        const ImGuiID frame_key = ImHashStr("VelaContentFrame", 0, root->ID);
        const ImGuiID time_key = ImHashStr("VelaContentTime", 0, root->ID);
        const int frame = ctx.FrameCount;
        int last = root->StateStorage.GetInt(frame_key, -2);
        if (last != frame && last != frame-1) root->StateStorage.SetFloat(time_key, static_cast<float>(ctx.Time));
        root->StateStorage.SetInt(frame_key, frame);
        const float t = enabled ? std::clamp((static_cast<float>(ctx.Time)-root->StateStorage.GetFloat(time_key))/.16f, 0.0f, 1.0f) : 1.f;
        const float alpha = opacity * ((root->Flags & ImGuiWindowFlags_DockNodeHost) ? 1.f : .2f+.8f*t*t*(3-2*t));
        for (ImDrawVert &vertex : window->DrawList->VtxBuffer) {
            const unsigned int a = (vertex.col >> IM_COL32_A_SHIFT) & 255;
            vertex.col = (vertex.col & ~(255u << IM_COL32_A_SHIFT)) | (static_cast<unsigned int>(a*alpha) << IM_COL32_A_SHIFT);
        }
    }
}
inline std::vector<ImRect> surfaces(ImGuiContext &ctx) {
    std::vector<ImRect> result;
    for (ImGuiWindow *window : ctx.Windows) {
        if (!window->Active || window->Hidden || window->Collapsed || window->IsFallbackWindow) continue;
        ImGuiWindow *root = window->RootWindow;
        ImRect rect;
        if (root->DockIsActive && root->DockNode) {
            auto *node = root->DockNode;
            rect = ImRect(node->Pos, ImVec2(node->Pos.x + node->Size.x, node->Pos.y + node->Size.y));
        } else {
            if (root != window || (window->Flags & (ImGuiWindowFlags_DockNodeHost | ImGuiWindowFlags_ChildWindow | ImGuiWindowFlags_Popup | ImGuiWindowFlags_Tooltip | ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_NoDocking))) continue;
            rect = ImRect(window->Pos, ImVec2(window->Pos.x + window->Size.x, window->Pos.y + window->Size.y));
        }
        bool duplicate = false;
        for (const auto &other : result) if (other.Min.x == rect.Min.x && other.Min.y == rect.Min.y && other.Max.x == rect.Max.x && other.Max.y == rect.Max.y) duplicate = true;
        if (!duplicate) result.push_back(rect);
    }
    for (size_t i = 0; i < result.size(); ++i)
        for (size_t j = i + 1; j < result.size();) {
            const auto &a = result[i]; const auto &b = result[j];
            const bool horizontal = std::abs(a.Min.y-b.Min.y)<1 && std::abs(a.Max.y-b.Max.y)<1 && (std::abs(a.Max.x-b.Min.x)<8 || std::abs(b.Max.x-a.Min.x)<8);
            const bool vertical = std::abs(a.Min.x-b.Min.x)<1 && std::abs(a.Max.x-b.Max.x)<1 && (std::abs(a.Max.y-b.Min.y)<8 || std::abs(b.Max.y-a.Min.y)<8);
            if (horizontal || vertical) { result[i].Add(b);result.erase(result.begin()+j);i=static_cast<size_t>(-1);break; } else ++j;
        }
    return result;
}
inline void backdrop(ImGuiContext &ctx, ImTextureID texture, float width, float height, bool flip, float alpha, float rounding) {
    ImDrawList *list = ImGui::GetBackgroundDrawList();
    for (const auto &rect : surfaces(ctx)) {
        ImVec2 a(rect.Min.x / width, rect.Min.y / height), b(rect.Max.x / width, rect.Max.y / height);
        if (flip) { a.y = 1.0f-a.y; b.y = 1.0f-b.y; }
        list->AddImageRounded(texture, rect.Min, rect.Max, a, b, IM_COL32(255,255,255,static_cast<int>(255*alpha)), rounding);
    }
}
}
