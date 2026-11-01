# Current implementation state

Recorded 2026-11-01. This file describes current behavior; use Git history for
implementation history and [the architecture map](ARCHITECTURE.md) for ownership.

## Appearance and preview

- Private MangoHud v10 extensions provide subtle noise, borders, shadows,
  inward padding and GPU backdrop blur on supported desktop GL/Vulkan paths.
- Shadow/padding changes preserve HUD anchors. SDR blur supports 8-bit and
  packed 10-bit surfaces; the user confirmed Stalker 2 SDR blur works.
- Surface-specific HDR color state fixes the user-confirmed Alt-Tab HUD issue.
  HDR backdrop blur remains disabled.
- The owned preview offers an animated frosted scene and generated day/night
  aerial images. Still images disable/dim Pause animation.
- Customization groups persist collapse state. Appearance edits affect only
  the private preview until explicit save; live frame limiting is separate.
- Preview captions reflect the loaded profile. Process switches protect
  unsaved appearance edits with Save/Discard/Cancel.

## Fonts and settings

- Full Google Fonts browsing uses cached metadata, bounded lazy previews,
  downloadable weights/italics and preserved licenses. Font tiles reveal with
  staggered fade/motion; numeric fields and weights ignore wheel changes.
- Both font fields open a local chooser. Identical main/additional files
  normalize to Same as main font. There is no additional-font context menu.
- The gear opens a compact frosted configuration modal. Advanced contains
  only private Vela MangoHud appearance options.

## ReShade

- Configure/Install entry tiles lead to a game chooser or five-step installer.
  Existing installations redirect to Configure. Closing resets to entry;
  active jobs finish in the background and prevent overlapping operations.
- Steam appinfo filtering excludes tools/runtimes while preserving games/demos
  and manual EXE browsing. Failed scans report an error and can be retried.
- Installation supports x86/x64 DirectX 9/10/11/12 and Windows OpenGL under
  Proton/Wine. Downloads are bounded; existing files are never overwritten.
- Configure has a blue game/action card, 25 searchable settings and an explicit
  dirty-state Save changes action. Writes preserve unrelated INI keys/comments,
  BOM/newlines and presets; stale snapshots and special/symlink files are rejected.
- Removal validates ownership. Ordinary removal preserves modifications;
  complete removal lists all owned/known ReShade files before confirmation.
- Shared finite validation pulses replace continuous red animation. Queued
  style synchronization fixes the reproduced xcb step-switch hang.
- The bundled unofficial ReShade 6.8.0.4 runtime rounds entire docked surfaces,
  offers Detach/Move controls and preserves font scale across resource resets.
  The default Vela theme uses 13-point fonts, alpha 0.7, white text, blue accents,
  disabled FPS counter and 400-nit HDR overlay brightness.

## HDR diagnostics

- Read-only session/desktop/driver information and KScreen display HDR/WCG,
  mode, refresh, scale and SDR brightness. The helper selects the real session
  even when Vela itself uses xcb inside Wayland.
- Refresh/copy, timeout, Unknown fallback and separate Qt geometry reporting.
  No monitor changes, game swapchain inspection or calibration tools.

## Refactor and validation

- First-party text, comments and documentation are English. Proper names and
  third-party licenses retain their original spelling.
- Python formatting/imports are standardized with Ruff; configuration is in
  pyproject.toml and optional tooling in requirements-dev.txt. CI runs lint,
  formatting, unit and isolated Qt smoke checks.
- ReShade widgets, navigation and workers are separate modules. Shared metric
  cards no longer live under the HDR-specific module name.
- Unit and offscreen/live-xcb GUI checks cover the Python changes. Native
  binaries were not rebuilt or changed by this refactor.
- Earlier native verification used owned Windows OpenGL x86/x64 and
  DirectX 11/DXVK test applications. Real Stalker 2 HDR/font-scale behavior
  still requires a game test; desktop Qt checks cannot establish it.

## Boundaries

- Native Linux/Windows Vulkan ReShade setup is not implemented.
- CSS game-HUD themes and Frosted Grid are not implemented. Qt's frosted
  material is a separate renderer from game backdrop blur.
- GL/Vulkan blur still depends on supported surface/present arrangements.
- Google metadata endpoints may change; bundled metadata/cache is the fallback.
- No commit, push, game-file replacement or native rebuild is part of this refactor.

- Vela ReShade 6.8.0.4 adds post-effect GPU backdrop blur, reversible open/close
  fades and tab-content activation fades. Configure/in-game Settings expose
  blur strength, sample quality, animation enable/duration. Both x86/x64 DLLs
  were rebuilt; existing game DLLs still require reinstallation. Owned tests
  passed OpenGL x86/x64, D3D11/DXVK SDR/scRGB/PQ, D3D12/VKD3D PQ, animation
  endpoints/bounds and real swapchain reset/font-scale checks. No game test or
  performance guarantee is implied. MangoHud HDR blur remains disabled.
