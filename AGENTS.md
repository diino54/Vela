# Vela: instructions for coding agents

## Start here

Vela is a Linux Python/PySide6 desktop controller for MangoHud, with an owned
native preview, private MangoHud extensions and an optional custom ReShade runtime.
The stable GUI entry point is `python3 -m vela.ui`. The project is not a web app;
CSS/HTML does not control the game overlays.

Before changing behavior, read:

1. [docs/UI_UX_PHILOSOPHY.md](docs/UI_UX_PHILOSOPHY.md): product principles, visual hierarchy, interaction and extension rules.
2. [docs/UI_DESIGN.md](docs/UI_DESIGN.md): implemented colors, geometry, timing and workflows.
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): module ownership and data flow.
4. [docs/STATE.md](docs/STATE.md): implemented capabilities and limitations.
5. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): dependencies, checks and native verification.

Read the relevant feature guide before changing fonts, ReShade or native code:
[Google Fonts](docs/GOOGLE_FONTS.md), [ReShade](docs/RESHADE.md),
[MangoHud native](native/README.md), [native testing](native/TESTING.md),
[ReShade native](native/reshade/README.md).

Use the actual repository root and inspect `git status` before editing. Do not
switch to a historical checkout or assume temporary native source trees still
exist. Preserve unrelated work, including uncommitted patches and binary outputs.
Existing documentation changes may also belong to ongoing work; read before editing.

## Non-negotiable behavior

- All first-party UI text, identifiers, comments, docstrings and documentation are
  English. Preserve proper names, font specimens and third-party license notices.
- Appearance changes affect only the private preview until explicit Save
  configuration. Runtime frame limiting uses a separate live Apply action.
- Preserve global/profile save choices, loaded-buffer identity and unsaved-change
  protection. Switching process must not redirect an old buffer's save target.
- Numeric controls, font weights and the alpha slider ignore mouse-wheel value
  changes. Open combo lists remain scrollable.
- Left-click either font field to choose a local file. Its catalog icon opens
  downloadable fonts. No additional-font context menu. Same-file aliases normalize
  additional font to Same as main font.
- Preserve dark frosted materials, compact modals and intentional animations.
  Visual cleanup must not flatten the design or remove lifecycle protection.
- Keep Simple for standard MangoHud options, Advanced for private Vela MangoHud
  effects, and Settings for application/configuration paths and inspection.
- Current HDR diagnostics are read-only. Unknown is not Disabled. Desktop HDR
  state is not evidence of a game's HDR swapchain or calibration.
- ReShade edits require explicit Save changes; filtering/loading does not write.
  Preserve unknown INI data and refuse stale saves after external edits.
- A hook DLL does not establish ownership. Never overwrite another mod or broaden
  removal scope without the established inventory/review/confirmation workflow.
- Do not capture unrelated desktop/game windows. Tests may capture their owned
  Qt/Wine windows or owned GPU buffers only.
- Do not truncate mapped native libraries. Publish complete binaries through a
  temporary file and atomic replacement, with matching build metadata/hashes.

## Where to change what

Paths below are relative to this repository. Keep state ownership in the owning
controller/backend; widget builders intentionally expose named controls without
maintaining a second configuration model.

| Task | Primary owner | Keep intact |
| --- | --- | --- |
| Main actions, explicit saves, lifecycle | vela/ui.py | Stable launcher, process identity, orderly shutdown |
| Three-column construction/wiring | vela/window_layout.py | Control creation order and preview space |
| Simple/Advanced appearance groups | vela/appearance_layout.py | Native option names and preview-only edits |
| Unsaved edits/process switching | vela/profile_switch.py | Original loaded target, Save/Discard/Cancel recovery |
| Global config/session I/O | vela/mangohud.py | Watchers, file identity, managed values, safe writes |
| Process/name helpers | vela/settings.py | Wine names and validation |
| Palette, QSS, root backdrop | vela/theme.py | Existing role selectors and cached grid |
| Frosted panel/material | vela/panels.py, vela/background.py | Cached subtle texture and rounded clipping |
| Shared input widgets | vela/controls.py | No-wheel behavior and minus/plus pattern |
| Section/layout primitives | vela/layout_helpers.py, vela/sections.py | Independent collapse preferences, retained values |
| Hover, glow, reveal | vela/animation.py | Paint-only feedback and queued invalid-field synchronization |
| Settings modal | vela/settings_dialog.py | Window-owned configuration handlers |
| Shared modal lifecycle | vela/modal.py | Owner snapshot, native-preview visibility, restore/cleanup |
| Google Fonts browser | vela/font_catalog.py | Paging, generations, bounded cache/loading |
| Font tiles/loader/weights | vela/font_widgets.py | Lazy specimens, wheel-safe selection |
| Font network/model/cache/licenses | vela/google_fonts.py | Bounded requests, offline fallback, licenses |
| Preview process/embedding | vela/preview.py | Owned process/window only and shutdown |
| Scene rendering/launch | vela/scene.py, vela/preview_runner.py | Private preview configuration and backgrounds |
| Status/save-choice cards | vela/notifications.py | Choice semantics and native stacking coordination |
| ReShade install/remove backend | vela/reshade.py | PE checks, staged installation, inventory, removal boundaries |
| ReShade modal coordination | vela/reshade_dialog.py | Navigation, dirty state, explicit actions, worker lifetimes |
| ReShade widget construction | vela/reshade_pages.py | Builder-only responsibility |
| ReShade page IDs/sizes | vela/reshade_flow.py | Named Page enum and compact per-page bounds |
| ReShade slow work | vela/reshade_workers.py | Queued signals and recoverable failures |
| ReShade INI parsing/saving | vela/reshade_config.py | Limited edits, original data, conflict/symlink checks |
| ReShade editable cards/search | vela/reshade_editor.py | Wheel safety, filtering without dirtying |
| ReShade theme preset | vela/reshade_theme.py | Separate native units; optional theme independent of runtime |
| Shared metric cards/icons | vela/metric_cards.py | Independent of HDR-specific models |
| Desktop HDR data/report | vela/hdr.py | Source/scope, timeout, Unknown fallback |
| HDR modal | vela/hdr_dialog.py | Asynchronous refresh and read-only behavior |
| Steam library discovery | vela/steam_library.py | Games/demos, tool/runtime filtering, manual fallback |
| Private game environment | vela/runtime.py | Process-private manifest/shim, system packages unchanged |
| Optional LSFG ordering | vela/layer_order.py | Explicit action and owned-file cleanup |
| Local install/launchers | scripts/install.py | Atomic libraries, dependency checks, correct package layout |
| MangoHud native effects | native/mangohud-background.patch | Reproducible pinned source delta |
| Custom ReShade runtime | native/reshade/ | Patch stack, shared headers, shaders, pinned upstream |
| Native builds | scripts/build_mangohud.py, scripts/build_reshade.py | Architecture/version/hash consistency |

## State and visual changes: working procedure

Before adding a setting, identify its renderer, units, range/default, loaded
state, dirty state, persistence target and failure mode. Reuse existing controls.
Trace one comparable option from widget to backend and test; then extend that
path. Do not create a new save mechanism inside a layout builder.

Before adding a modal/page, define bounds, scrolling, Back/Close/Escape, reset
behavior and worker ownership. Prefer FrostedModal. The font browser retains its
own established coordinator. ReShade page bounds belong in reshade_flow.py.
Before changing motion, define interruption and cleanup, not only the happy path.

For a refactor, preserve signal ordering, process identity and persistence first.
Extract cohesive responsibilities rather than splitting arbitrary line ranges.
Do not move state into UI builders, perform disk I/O in paintEvent, or add blocking
network/scanning to GUI slots. Add comments explaining ownership/invariants and
non-obvious failure prevention rather than narrating every line.

## Known failure modes: do not reintroduce

### Qt/native stacking and callbacks

Native GL children can cover ordinary Qt overlays. Snapshot only the owned Vela
surface, hide the live preview while a modal is open and restore its previous
visibility on close/interruption. Restore background enabled state too. Never
resurrect an already closed preview during shutdown.

Font load/reveal callbacks need generation/lifetime checks. Preserve pagination,
lazy specimens and bounded batches. Do not register every catalog font at once.

### Validation and Qt style propagation

Use FieldGlow for invalid inputs and confirmations: one gentle 1100 ms pulse
per failed attempt, then static subtle red border/tint with bright readable text.
A repeat attempt retriggers; correction restores the original style. ButtonGlow
is the separate 2400 ms available-action blue pulse.

FieldGlow Show/Hide/EnabledChange synchronization must remain queued, coalesced
and reentrancy-guarded. Never synchronously restore styles during Hide propagation
or reapply an identical stylesheet: this caused a reproduced xcb polish hang.
Checkbox hover painting uses Qt's actual indicator rectangle, not hardcoded bounds.

### Workers and reset

Workers never mutate Qt widgets. Cross-thread results use queued signals.
Retain workers until finished, including failed library scans. Closing ReShade
resets choices/navigation but active work completes; late results cannot navigate
a reset screen to Ready. Avoid overlapping operations and premature QThread deletion.

### Files and native resources

Preserve MangoHud configuration inode/watch behavior (`replace_watched`) and
symlink protections. Do not replace it with generic atomic replacement: that can
break live watching. ReShade INI uses its own conflict-checked atomic write path;
these two file contracts are intentionally different.

MangoHud v10 supports supported SDR blur, including packed 10-bit SDR. Its HDR
blur remains disabled; preserve per-surface color-state isolation and HUD anchors.
ReShade v4 has a separate GPU backdrop supporting tested SDR/scRGB/PQ paths.
Read its native guide for API/format fallbacks. Neither Qt screenshots nor a
10-bit format alone verifies HDR. Never save transient animation alpha or mutate
persistent font scale during swapchain reset.

PySide6 6.12.0 is excluded because of a reproduced None reference-ownership crash
on Python 3.11. Keep requirements, installer checks and runtime probe consistent.
Do not hide this by disabling animation or skipping tests.

## Verification by change type

For Python behavior changes, run the base checks from the repository root:

```sh
ruff check vela scripts tests
ruff format --check vela scripts tests
python3 -B tests/check_qt_runtime.py
python3 -B -m unittest discover -s tests -q
```

Then select relevant integration checks:

| Change | Additional validation |
| --- | --- |
| Main widgets, controls, fonts, modals | QT_QPA_PLATFORM=offscreen python3 -B tests/check_ui.py |
| Profiles, save target, process switching | QT_QPA_PLATFORM=offscreen python3 -B tests/check_profile_switch.py |
| ReShade wizard/editor/validation | QT_QPA_PLATFORM=offscreen python3 -B tests/check_reshade.py |
| Style propagation/step switching | QT_QPA_PLATFORM=xcb timeout 35 python3 -B tests/check_reshade.py; needs a graphical session |
| Desktop HDR report/modal | QT_QPA_PLATFORM=offscreen python3 -B tests/check_hdr.py |
| Native MangoHud | Native guide and owned blur/padding/anchor/color-state tests |
| Native ReShade | Native guide, clean patch application, matching DLLs/metadata, owned harness/visual/reset checks |
| Documentation only | Check links, module names, stated values and git diff --check; no native rebuild needed |

Use temporary preferences, synthetic games and mocked network in automated GUI
checks. Run native tests only in owned harnesses, never against unrelated windows.
Test interrupted loading, rapid navigation, small dimensions and long paths when
relevant. Offscreen tests do not establish real GL stacking, xcb behavior, game
HDR, Alt-Tab compatibility or performance. State these limits in delivery.

Do not rewrite tests to mirror a new implementation or remove meaningful checks
to make a regression disappear. Add focused behavioral coverage for new failure
modes. Use DEVELOPMENT.md and script --help for native commands, not guessed flags.

## Documentation and delivery

Keep this file as an operational map. Update UI_UX_PHILOSOPHY for principles,
UI_DESIGN for visible geometry/interaction contracts, ARCHITECTURE for ownership,
STATE for current capabilities and DEVELOPMENT for reproducible checks. Link to
feature/native guides rather than copying long build instructions into each file.
Source code is authoritative for current values; update stale docs instead of
changing behavior merely to match historical prose. Do not describe proposals as
implemented or test harness success as user-confirmed game compatibility.

For documentation-only work, installation is unnecessary. For application changes
when the user expects the local app updated, use `python3 -B scripts/install.py`.
Explain restart requirements: Vela for installed Python code, games for native
libraries. Installing Vela does not automatically replace game-local ReShade DLLs.
Do not install into real games, modify Steam settings or replace system libraries
as an incidental test. Do not commit, squash, force-push or publish unless requested.
