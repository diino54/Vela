# Vela ReShade: rounded outer docking surface

Pinned ReShade **6.8.0**, revision
`18deaa52de0c425a78b329e9cb3c497281cd00ec`, and its exact ImGui submodule
`3912b3d9a9c1b3f17431aebafd86d2f40ee6e59c`. This is an **unofficial modified
runtime**, separate from the official runtime offered by the installer.
Both x86/x64 outputs live in `vela/native/reshade`, with SHA-256 and source
revision in BUILD.json. The installer validates hashes/architecture first.
No existing game DLL is automatically overwritten.

## Rendering approach

`rounded-ui.patch` adds one post-render call in runtime_gui.cpp.
`vela_rounding.hpp` processes ImGui draw geometry after `ImGui::Render()` and
before upload. Identify active docked panels and their child/host draw lists,
merge adjacent rectangular panes, and cut only the four external corner
squares. Triangle clipping interpolates texture coordinates and RGBA colors;
a one-pixel alpha fringe smooths the arc. Original texture IDs, scissors,
callbacks, order, and vertex/index offsets remain valid. Index data are still
16-bit, using per-part VtxOffset for generated vertices. Floating windows,
popups and the OSD are not rounded by this pass. They keep upstream behavior.

The radius is `[STYLE] WindowRounding`, already 12 in the Vela UI preset.
Zero disables the pass. No game-frame capture, blur, extra render target or
API-specific clipping shader is used. The pass runs only with the overlay open.
ImGui layout and input hit regions remain rectangular, including the tiny
transparent corner cutouts; this is a rendering change, not hit-test shaping.
Adjacent rectangles merge; non-rectangular/more elaborate docking layouts may
remain separate surfaces. This is not an OS window decoration.

`clang-build.patch` contains separate Linux/clang-cl build compatibility changes:
standard add-on mode 1, case-correct SDK library names, LLVM RC path/copyright
encoding, local F16C/SSE4 wrappers for existing HDR screenshot conversion,
fpng instruction flags, proper global declarations and MinHook memcpy/memset
substitutions. It does not disable HDR or screenshot support. English UI is
compiled; localization resources are not enabled in this cross-build.

## Build on Linux

Build tools are isolated in Podman; Microsoft SDK/MSVC stay in the work folder
and are never copied into Vela or games. Host prerequisites: Podman, Python,
Git and Wine. A container must mount the chosen work folder as `/work`.

```sh
mkdir -p /tmp/vela-reshade-work
podman run -d --name vela-reshade-build -v /tmp/vela-reshade-work:/work:Z registry.fedoraproject.org/fedora:44 sleep infinity
podman exec vela-reshade-build dnf install -y clang lld llvm cmake ninja-build gcc-c++ msitools cabextract python3 git python3-pip
git clone https://github.com/mstorsjo/msvc-wine.git /tmp/vela-reshade-work/msvc-wine
git -C /tmp/vela-reshade-work/msvc-wine checkout 514f8ea34842cd6d831804d0e9658d3a32870ae1
```

Obtain the Microsoft toolchain using msvc-wine's `vsdownload.py` (Microsoft
license acceptance is part of that tool). The verified environment used MSVC
14.44.35207 and Windows SDK 10.0.26100.0, x64 host tools, with both x64/x86
libraries. Host-tool wrapper setup:

```sh
podman exec vela-reshade-build python3 /work/msvc-wine/vsdownload.py --major 17 --accept-license --architecture x64 --with-workload no --with-asan no --with-atl no --with-dia no --with-msbuild no --dest /work/msvc
podman exec vela-reshade-build sh /work/msvc-wine/install.sh /work/msvc
python3 -B scripts/build_reshade.py
```

The script verifies source revisions, applies patches (or verifies they are
already applied), copies the owned header, generates version metadata, creates
SDK filename aliases for Linux, compiles original HLSL resources using native
SDK FXC via a separate Wine prefix, then builds both architectures. It copies
DLLs atomically; `--arch x64` / `x86` can build individually. `--skip-shaders`
is for reusing already generated, unchanged original shaders. Compiler/SDK
updates can change binary hashes; record final BUILD.json alongside DLLs.
The build source lives outside the repo; patches and the header are authoritative.

## Tests

Compile the real pinned ImGui without a GPU for geometry/mesh checks:

```sh
imgui=/tmp/vela-reshade-work/source/deps/imgui
g++ -std=c++17 -O2 -I"$imgui" native/reshade/rounding_test.cpp "$imgui/imgui.cpp" "$imgui/imgui_draw.cpp" "$imgui/imgui_widgets.cpp" "$imgui/imgui_tables.cpp" -o /tmp/vela-reshade-rounding-test
/tmp/vela-reshade-rounding-test /tmp/vela-reshade-rounding
/tmp/vela-reshade-rounding-test /tmp/vela-reshade-rounding-split split
```

This checks merged panes, unchanged floating windows, feathering, radius zero,
valid indices and counts. It writes actual ImGui software-rasterized PPMs,
not illustrative mockups. A tiny tolerance covers float interpolation on
isolated shared edges of the CPU rasterizer. Sample CPU time for clipping this
small test mesh was about 0.16–0.20 ms; this is not an in-game benchmark.

`tests/check_reshade_native.py` builds a small owned Windows OpenGL or D3D11
program, loads the bundled DLL under Wine and opens the overlay by posting Home
to its own window. OpenGL capture verifies XRes PID and a per-run ownership
marker. D3D11 exports only its own staging texture, also supporting Wayland. It creates
an isolated test folder/prefix and never changes a real game installation.

```sh
python3 -B tests/check_reshade_native.py --api opengl --bits 64
python3 -B tests/check_reshade_native.py --api d3d11 --bits 64 --dxvk /path/to/dxvk/x86_64-windows
```

The DXVK directory is read-only input; its DLLs are copied only into the
private test prefix, never into a game or a global Wine prefix. Wine 11.20
builtin D3D11 failed ReShade empty-texture initialization on this machine;
use DXVK for this smoke.

Run Python unit/UI tests as documented in DEVELOPMENT.md. Real Proton/HDR/game
injection remains a separate verification step; don't infer it from a CPU mesh
test or a Wine OpenGL test. Custom binaries are unsigned; the official runtime
remains selectable for games requiring the official build.

Verified on 2026-11-01: x86/x64 DLL builds, both patches on clean upstream
files, CPU single/split dock geometry, Wine OpenGL x86/x64, and Wine + DXVK
DirectX 11 x64 with an owned staging-texture capture. No Stalker or HDR claim
is implied by these SDR test applications.

## Detachable panels (Vela build 6.8.0.2)

The callback pages expose **Detach panel**, which queues a context-owned request.
Before the next NewFrame docking update, detach the selected entire leaf dock node with all
its tabs, stop automatic mouse capture, offset it to (24,24), and clamp its size
to the viewport. A floating group exposes **Move panel**, a drag handle wired to
ImGui's own window/node movement. This also works when tabs leave no empty
space in the tab bar. Requests live in the owning ImGuiWindow StateStorage;
there is no process-global pending pointer or interference between runtimes.
The native geometry regression checks preserved tabs and actual mouse-driven
movement after detachment, in single/split layouts. Rounding is retained.

## Stable font scale (Vela build 6.8.0.3)

Upstream init_imgui_resources reapplies a height-dependent font multiplier
whenever FontSize is 13, even when STYLE/FontScale explicitly specifies 1.
Resource recreation can therefore change the visible text size without
changing the displayed FontSize. Vela's vela_font_scale.hpp preserves a valid
explicit or already resolved multiplier. Resolution-derived defaults are only
chosen before the context's first GUI frame. Intentional custom scale and
legacy zero-scale configuration remain supported. It does not freeze the
configured font size or disable intentional Ctrl+wheel scaling.

Each resource initialization records base font size, main scale, DPI scale,
context frame and surface dimensions in ReShade.log as `Vela font state`.
This diagnoses reset behavior without polling or logging every frame. It is a
specific fix for resource-init scaling; user-reported Stalker 2 Alt-Tab behavior
has not yet been confirmed fixed in that game.

```sh
g++ -std=c++17 -O2 native/reshade/font_scale_test.cpp -o /tmp/vela-reshade-font-scale-test
/tmp/vela-reshade-font-scale-test
python3 -B tests/check_reshade_native.py --api d3d11 --bits 64 --font-reset-check --dxvk /path/to/dxvk/x86_64-windows
```

The GPU regression resizes the actual DXGI swapchain from 960x640 to 960x1440
and 960x1080 while FontSize=13 and FontScale=1. It verifies resource reinitialization
logs retain scale 1 throughout. It is not a physical Alt-Tab or HDR game test.
