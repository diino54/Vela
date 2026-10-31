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

## Fast checks

```sh
python3 -B -m unittest discover -s tests -q
QT_QPA_PLATFORM=offscreen python3 -B tests/check_ui.py
```

The first command covers config parsing/serialization and Google Fonts data
contracts. The second runs the real Qt window with network and owned preview
startup disabled, temporary preferences, category/search/weight interactions,
loader cancellation, and preview restoration. It can export only its own Qt
widgets with `--screenshots /tmp/vela-ui-check`. It does not verify actual GL
embedding, GPU rendering or live network endpoints.

Tests are tracked in the repository; `__pycache__` and test-tool caches are
ignored. Before this refactor tests existed locally but were ignored by Git.

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
