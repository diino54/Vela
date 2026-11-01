# ReShade integration

The experimental panel's **Set up ReShade…** button opens Configure/Install entry tiles, with a five-step installer under Install
for Windows games under Proton/Wine. Select an installed Steam game to browse
its executable, or browse manually. Select the actual rendering executable
(e.g. `Binaries/Win64/*Shipping.exe`), its API and shader collections, optionally
import a preset, review the plan and confirm installation with the game closed.

Supported hooks: DirectX 9 (`d3d9.dll`), DirectX 10/11/12 (`dxgi.dll`), Windows
OpenGL (`opengl32.dll`). PE headers detect x86/x64; ARM and native Linux targets
are rejected. A DirectX game translated through DXVK/VKD3D still needs its
DirectX hook. Windows Vulkan requires a different layer/prefix setup and is
not implemented. Native Linux Vulkan/vkBasalt is a separate feature.

## Sources and configuration

- **Rounded outer window · Vela ReShade**, selected initially, uses the bundled
  unofficial x86/x64 6.8.0 build. It verifies the DLL SHA-256 and PE architecture,
  then installs it through the same exclusive/journaled flow. Disabling this
  option uses the official runtime instead. See [native renderer/build details](../native/reshade/README.md).
- [Official ReShade download](https://reshade.me/): resolve the latest **standard**
  setup URL at install time, download via HTTPS, extract its appended ZIP with
  Python, validate the selected DLL's PE architecture. Never execute the setup.
- [Upstream setup implementation](https://github.com/crosire/reshade/blob/main/setup/MainWindow.xaml.cs)
  documents the embedded `ReShade32.dll` / `ReShade64.dll` archive and API hooks.
- [Standard utilities](https://github.com/crosire/reshade-shaders/tree/slim),
  [SweetFX](https://github.com/CeeJayDK/SweetFX),
  [qUINT](https://github.com/martymcmodding/qUINT): downloaded from their authors'
  GitHub archives at installation time. Keep their README/license files beside
  shaders and textures. Standard + SweetFX are selected initially.

The DLL, `ReShade.ini`, `VelaPreset.ini`, `vela-reshade-shaders/` and
`.vela-reshade.json` are local to the selected executable. The generated INI
points at each selected shader/texture directory recursively. The initial empty
preset enables no techniques. Importing a preset does not fetch arbitrary
custom dependencies. ReShade's own menu (Home) configures effects after launch.

The final page generates `WINEDLLOVERRIDES="<hook>=n,b"` with a single
`%command%`. The final page supplies a minimal command. Review contains no launch-options
editor or command preview. Users with existing wrappers such as `vela-mangohud`
should retain them when adding the displayed DLL override in Steam.
Vela never edits Steam's settings or Wine registry. It does not install compiler
DLLs into prefixes; if shaders fail to compile, the ready page points to
`d3dcompiler_47` installation with Protontricks in the game's own prefix.

## Files, failure and removal

`reshade.py` has no Qt dependency. It bounds downloads/extraction and rejects
archive traversal. Validate before network access, prepare downloads in memory,
revalidate, stage under a temporary folder on the destination filesystem, then
publish using exclusive hard links. Existing DLL/config/shader installations,
including conflicting hook DLLs from other mods, cause an error. No file is
silently replaced. An interrupted publication rolls back files created by this
operation. A process crash/power loss during publication is not a journaled
recovery transaction; inspect any partial files before retrying.

The final ownership journal records SHA-256 hashes. Removal validates its paths
before deleting anything and removes only unchanged owned regular files.
Modified configuration/presets/shaders are retained and listed, with the reduced
journal retained for later inspection. Other game files remain untouched.
Automatic migration/update of existing installations is not implemented.

`reshade_dialog.py` owns the wizard, animation and QThreads. Worker signals use
explicit queued connections to Qt slots on the GUI thread. Completion prepares
the ready page before switching; the stack opacity effect is disabled after each
transition to avoid stale scroll/text viewport rendering. Closing the panel
leaves any active operation alive; reopening always starts at the Configure/Install entry screen. Continue
is disabled until that operation finishes, preventing overlapping installs.
A background completion does not pull the reopened wizard away from the entry screen. Vela's main
window refuses shutdown while either installer or library worker is active,
preventing QThread destruction mid-operation. No Steam game is installed merely
by opening the wizard. Steam library indexing reads only local manifests.

Validation: unit fixtures cover install/remove/failure paths; `check_reshade.py`
exercises the actual Qt wizard and worker threads offline. Live ReShade 6.8.0
32/64-bit runtime and all three upstream shader archives were downloaded and
parsed on 2026-11-01. Actual game injection still needs a user game test.

## Optional Vela UI preset

Effects includes **Apply Vela UI theme**, initially checked and summarized in
Review. Disabling it leaves ReShade's default UI configuration untouched.
The choice writes only the newly created game-local ReShade.ini:

- Custom Advanced palette (`StyleIndex=4`), charcoal backgrounds, gray controls,
  white text (#ffffff), brighter disabled text (#b8b8b8), global alpha 0.7,
  blue #246bce accents; dark text-editor style.
- Window/child/popup rounding 12, control/tab/scrollbar rounding 7.
- Global font size and text editor font size both 13, font scale 1.
- `[OVERLAY] ShowFPS=0`.
- `[STYLE] HdrOverlayBrightness=400`, the ReShade 6.8 UI slider's maximum nits.

These use the keys read by upstream runtime_gui.cpp. ReShade renders with
ImGui: the preset matches palette and rounding, without implementing Qt's
frosted texture or Vela animations. It does not change game HDR output or
shader parameters. Existing installations are not modified by this installer.
The extracted helper `reshade_theme.py` owns these defaults and RGBA mapping.

## Complete removal

When a Vela installation is detected, Remove ReShade offers an optional
**Delete everything, including modified presets and shaders** checkbox. The
review lists the files and resets confirmation when the removal mode changes.
The default still preserves modifications. Full removal deletes modified
journaled files, game-local ReShade.ini/VelaPreset.ini, the installed hook,
ReShade.log/ReShade.log.old, the entire dedicated vela-reshade-shaders tree
(including manually added files), and the ownership journal. Other root-level
presets or mods are outside this installation's ownership and are untouched.
Symlinks and invalid journals reject the operation before deletion. This
operates on detected Vela installations; arbitrary third-party installations
are still not adopted automatically.

## Rounded whole-window rendering

The installer can use the bundled Vela ReShade build independently of the palette
checkbox. Its geometry pass clips the entire docked surface, including tab bar,
backgrounds and child content. Adjacent rectangular panes share outer corners.
Floating windows/popups retain upstream rounding. The radius follows
`WindowRounding` (12 by default); zero disables the pass. With the Vela palette
unchecked, the installer writes only that rounding value while retaining the
standard ReShade palette. Runtime selection/version appears in Review.

The ownership journal records `runtime=vela-rounded` or `official`. Runtime
license notices are installed under vela-reshade-shaders/runtime as owned files.
An existing installation must be removed before reinstalling the new runtime;
opening the wizard never replaces a running game's DLL.

Steam selection uses local appinfo common/type metadata (cache versions 27–29)
to show games/demos and exclude tools, applications and DLC. With unavailable
metadata, narrow fallback filters hide known Steam runtimes and helper apps.
The manual executable chooser remains available. steam_library.py owns this
read-only parsing and performs no network request.

Configure owns the removal action and exposes the game directory and ReShade.ini via the default desktop editor. Install automatically redirects to Configure when the selected executable folder already contains ReShade/hook files. A protected hook alone is described as a possible graphics hook, not proof of ReShade. External installations are detected but automatic removal still requires a valid Vela ownership journal. Back from removal review returns to Configure. Page indexes 0–4 remain the installation steps, 5 is the entry chooser and 6 is Configure; mode tracks the current branch.

Configure now offers editable two-column cards: UI theme (preserve current / Vela / ReShade Default), global alpha with slider, global/editor font size, window corner rounding, HDR overlay brightness and Show FPS. Save changes pulses only when dirty; changes need a game restart. Palette selection preserves numeric controls and preset paths. WindowRounding affects whole docked surfaces only with the custom Vela runtime; switching runtime still requires installation.

`reshade_config.py` reads at most 2 MiB, rejects symlinks/nonregular files, preserves unknown keys, comments, BOM and newline style, and changes only edited keys. Saving compares the current bytes to the loaded snapshot, then publishes through a same-directory temporary file with original mode. Concurrent external edits require reopening Configure. The ownership journal is intentionally not updated: an edited INI remains modified and is preserved by ordinary removal. Explicit complete removal still deletes it. Tests use temporary files, never user game configurations.

Configure now contains 21 searchable cards. Added font/FPS scales, child/popup/control/grab/scrollbar/tab rounding, clock, frame time, preset name, screenshot notifications, auto-save preset and variable tabs. Search matches all entered words against the setting label/key and does not change dirty state. Numeric editors hide native spin arrows, retaining shared −/+ controls; wheel events still cannot change values. Saving keeps the current search query.
