# Vela: working guide for the next agent

Read `docs/ARCHITECTURE.md`, `docs/UI_DESIGN.md`, `docs/DEVELOPMENT.md` and
`docs/STATE.md` before changing behavior. This file is the short entry point;
the README is user-facing, not the architecture reference.

## Project and responsibilities

- Work in this repository. Do not use the removed Dropbox checkout or assume
  temporary `/tmp` native sources still exist.
- Python/PySide6 desktop app; GUI entry point stays `python3 -m vela.ui`.
- `ui.py`: window actions/state, explicit saves, selected process, shutdown.
- `profile_switch.py`: loaded-buffer baseline and save/discard/cancel process switching.
- `window_layout.py`: three-column construction and signal wiring.
- `appearance_layout.py`: standard Simple controls and Vela-only Advanced effects.
- `settings_dialog.py` / `modal.py`: gear configuration page and frosted modal shell.
- `reshade_config.py` / `reshade_editor.py`: conservative ReShade.ini updates and editable Configure cards; explicit Save changes, preserve unknown keys/presets and reject stale saves.
- `reshade.py`: game-local installation, ownership journal and removal.
- `reshade_dialog.py`: ReShade coordinator; `reshade_pages.py`: widget construction; `reshade_flow.py`: named pages and panel limits; `reshade_workers.py`: background I/O.
- `hdr.py` / `hdr_dialog.py`: read-only session/display HDR diagnostics; async KScreen query and unknown fallback.
- `metric_cards.py`: shared HDR/ReShade metric cards and icons.
- `controls.py`, `layout_helpers.py`: reusable controls/layout primitives.
- `theme.py`, `panels.py`, `background.py`, `animation.py`: visual system.
- `font_catalog.py`: browser coordinator; `font_widgets.py`: leaf controls.
- `google_fonts.py`: catalog model, network, licenses, caches.
- `mangohud.py`: process/config control; `preview.py`: owned native preview.
- `native/reshade/`: pinned ReShade 6.8 rounded docking geometry and separate cross-build patch; `scripts/build_reshade.py` builds both DLLs.
- `native/mangohud-background.patch`: source of truth for native extensions.

## Behavioral constraints

- Appearance changes update the private preview first. Only explicit Save
  configuration persists appearance to global/game profiles.
- Runtime frame limiting is a separate Apply action. Preserve game identity
  checks and global-versus-profile save selection.
- Never change numeric fields or font weights on mouse-wheel events. Open
  combo lists remain scrollable. This is an explicit user preference.
- Left-click on either font field opens the local file chooser; no additional
  font context menu. Identical main/additional files normalize to inheritance.
  The catalog icon provides downloadable fonts.
- Keep all first-party UI text, comments, docstrings, identifiers and documentation in English. Preserve proper names, font specimens and third-party license notices.
- Preserve the dark frosted panels and animations; don't flatten the design.
- Native GL child windows stack above ordinary Qt siblings: the font modal
  snapshots/dims the owner and temporarily hides the preview. Restore it
  after closing, including interrupted animations.
- Delayed font loading/reveal callbacks require generation checks. Don't
  register every font or build thousands of tiles at once.
- Do not truncate mapped native libraries. Installation/build output uses
  temporary files plus `os.replace`.
- Preserve configuration inode/watch behavior (`replace_watched`) and symlink
  protections. Do not replace it with naive atomic config-file replacement.
- HDR blur is disabled; 10-bit SDR blur is supported. HDR HUD colors are a
  separate feature. Keep v10's surface/config color-state isolation.

## Validation and delivery

Run `ruff check vela scripts tests`, `ruff format --check vela scripts tests`,
and `python3 -B -m unittest discover -s tests -q` and, for UI changes,
`QT_QPA_PLATFORM=offscreen python3 -B tests/check_ui.py`. The UI smoke uses no
network, game windows or real preference writes. See DEVELOPMENT for native
and live-download checks. Never capture unrelated desktop windows; native
capture helpers restrict themselves to the test process's owned window.

Install completed changes with `python3 -B scripts/install.py` when the user
expects the local app updated. Running Vela/games need restarting for new code
or libraries. Do not commit, squash or push unless the user requests it.
