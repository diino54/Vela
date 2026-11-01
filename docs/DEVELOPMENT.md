# Development and validation

## Run and install

Use Python 3.11+ and PySide6 6.6+ on Linux, with system MangoHud installed.
From the repository root:

```sh
python3 -B -m vela.ui
python3 -B scripts/install.py
```

Installation creates `~/.local/bin/vela` and `vela-mangohud` and copies the
Python package into `~/.local/share/vela/vela`. Restart Vela after changing
installed UI code; restart games after changing native libraries.

For private renderer features, launch a game with `vela-mangohud %command%`.
The user's Stalker setup also used `PROTON_ENABLE_WAYLAND=1 gamemoderun` before
that command. Plain `mangohud` loads the system backend and lacks Vela extras.

## Python quality and fast checks

The project uses English for first-party UI labels, comments, docstrings and
documentation. Preserve proper names and upstream license notices.
For pip-based development, install the runtime and quality tools in a virtual environment:

```sh
python3 -m pip install -r requirements-dev.txt
ruff check vela scripts tests
ruff format --check vela scripts tests
python3 -B tests/check_qt_runtime.py
python3 -B -m unittest discover -s tests -q
QT_QPA_PLATFORM=offscreen python3 -B tests/check_ui.py
QT_QPA_PLATFORM=offscreen python3 -B tests/check_profile_switch.py
QT_QPA_PLATFORM=offscreen python3 -B tests/check_reshade.py
QT_QPA_PLATFORM=offscreen python3 -B tests/check_hdr.py
```

Use `ruff format vela scripts tests` to apply formatting. Rules are intentionally
small: syntax errors, unused/undefined names, imports and statement structure.
Platform/path setup exceptions for entry points and isolated GUI tests are explicit.
The GitHub Python quality workflow runs the same checks using Python 3.11.

Unit tests cover configuration parsing, native option contracts, Steam metadata,
HDR reporting, font data and ReShade installation/settings ownership. Qt smokes
use temporary preferences, synthetic game files and mocked network/preview startup.
They never install into real games or alter real display settings. Optional
`check_ui.py --screenshots /tmp/vela-ui-check` exports only its owned Qt widgets;
this does not verify actual GL embedding, native rendering or game HDR.

Tests are tracked; caches and bytecode are ignored. See [the refactor audit](AUDIT.md)
for findings, regression cases and the limits of the current validation.

## Native changes

```sh
python3 -B scripts/build_mangohud.py --container
python3 -B scripts/install.py
```

The build verifies upstream commit
`a37b007e8018738270c9282c3a53b0ed7e786bcf` and applies the native patch. Read
`native/README.md` before editing it. Keep all new native headers in the patch;
reverse-check against the modified source tree and test applying it to a clean
checkout. Match binary artifacts, BUILD.txt and build-script version metadata.

`native/color_state_test.cpp` checks color-context/cache invalidation without
a game. The manual `tests/check_hud_blur.py`, `check_hud_padding.py` and
`check_hud_anchor.py` exercise real renderers; they need graphical access and,
for Vulkan blur, the checker binary built from `tests/blur_checker_vulkan.cpp`.
Read each script's CLI/help rather than guessing flags. Legacy anchor captures
require focus; newer capture helpers identify only the test process's window.
Never capture another application's desktop contents as a test shortcut.

## Regressions to check

- Appearance edits preview only; explicit saves retain global/profile choice.
- Config file watchers keep working after edits; game identity and symlinks
  remain protected.
- Main/Additional font selection, no wheel changes, catalog filtering/paging,
  offline cache and network failure recovery.
- Open/close the font modal during loading and during a reveal; resize it,
  switch categories quickly and restore the native preview afterward.
- Native appearance changes preserve HUD anchors; padding expands inward
  content insets; blur leaves text sharp and restores exact output when off.
- HDR Alt-Tab must be checked in a real HDR game after native changes. An
  offscreen Qt screenshot cannot establish HDR correctness.

## Paths and ownership

MangoHud profiles live under the selected/global config paths. Font files and
licenses use `$XDG_DATA_HOME/vela/fonts`, metadata/specimens use
`$XDG_CACHE_HOME/vela/google-fonts`, and QSettings owns Vela window/preferences.
The preview uses a temporary owned configuration. The launcher creates a
process-private explicit Vulkan manifest and preloads the private GL shim;
system MangoHud packages are not overwritten. LSFG ordering is separate and
only configured through the explicit Fix LSFG action.

ReShade tests use synthetic PE/ZIP fixtures and temporary game folders. They cover
rollback, existing-mod protection, architecture checks, unsafe ZIP/journal paths,
modified-file retention, launch options and the real threaded wizard. Live upstream
download/extraction was also checked; running a game remains a separate integration test.
See [ReShade integration](RESHADE.md) for boundaries and ownership.

For whole-window ReShade rounding, see [native/reshade/README.md](../native/reshade/README.md).
`python3 -B scripts/build_reshade.py` reproduces x86/x64 DLLs using the documented
SDK/Podman environment; this does not rebuild MangoHud. Native tests compile
pinned ImGui and use owned Windows OpenGL/D3D11 harnesses. Never infer HDR/game
compatibility from the CPU geometry test.

HDR diagnostics: `QT_QPA_PLATFORM=offscreen python3 -B tests/check_hdr.py` tests local subprocess fixtures, missing backend, timeout, copy and owned-process cleanup. Add `--screenshots` to export only the test window. `tests/test_hdr.py` tests HDR enabled/disabled/missing fields. Live `kscreen-doctor -j` is read-only; session QPA must be Wayland on Wayland even if Vela itself uses xcb. Field source: https://github.com/KDE/libkscreen/blob/master/src/configserializer.cpp. Reports cannot establish game swapchain HDR.

FieldGlow regression: `QT_QPA_PLATFORM=xcb timeout 35 python3 -B tests/check_reshade.py` exercises real XWayland rendering and rapid Effects/Review transitions with an event-loop heartbeat. Offscreen tests alone did not catch a Qt stylesheet-polish hang when FieldGlow restored a stylesheet synchronously inside Hide event propagation. Keep show/hide/enabled synchronization queued, coalesced and guarded; never reapply an identical stylesheet. The pre-fix live test hung in FieldGlow.sync → QWidget.setStyleSheet/inheritStyle; the fixed live test passed.

## Qt dependency compatibility

`requirements.txt` is the source of truth for pip-based Qt dependencies;
`requirements-dev.txt` includes it. Distribution/system installs remain supported
when their Qt version is compatible. PySide6 6.12.0 is excluded and the installer
rejects it: wrapped void calls lose references to None on CPython 3.11, eventually
causing a fatal `none_dealloc` abort. This was reproduced with 128 calls to
QPainter.setRenderHint (reference delta -128); the same probe returned 0 with a
clean Python 3.11.18/PySide6 6.11.3 environment.

Run `tests/check_qt_runtime.py` before GUI smokes. It prints Python/PySide/Shiboken
versions and performs a bounded ownership probe so a broken binding fails clearly
without exhausting the interpreter's reference count. The CI workflow uses the
shared dependency list and declares the native Qt/OpenGL/QtNetwork libraries.
All workflow checks passed in an isolated Python 3.11 environment after this fix.
A new hosted GitHub Actions run is still needed after committing/pushing it.

Native visual tests: compile native/reshade/visual_test.cpp with the pinned
ImGui sources, then run owned checker smokes with --visual-check and optional
--hdr scrgb/pq. Use --blur 0 for the comparison run. The frame verification
script accepts --blur/--no-blur checkpoint directories and repeated --hdr dirs.
The harness atomically exports its own buffers; never capture unrelated windows.
DXVK/VKD3D input libraries are copied only into the private Wine test prefix.
The build container additionally needs glslang for the Vulkan shader variant.
