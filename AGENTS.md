# Vela: working guide for the next agent

Read `docs/ARCHITECTURE.md`, `docs/UI_DESIGN.md`, `docs/DEVELOPMENT.md` and
`docs/STATE.md` before changing behavior. This file is the short entry point;
the README is user-facing, not the architecture reference.

## Project and responsibilities

- Work in this repository. Do not use the removed Dropbox checkout or assume
  temporary `/tmp` native sources still exist.
- Python/PySide6 desktop app; GUI entry point stays `python3 -m vela.ui`.
- `ui.py`: window actions/state, explicit saves, selected process, shutdown.
- `window_layout.py`: three-column construction and signal wiring.
- `appearance_layout.py`: metric/appearance fields keyed by MangoHud option.
- `controls.py`, `layout_helpers.py`: reusable controls/layout primitives.
- `theme.py`, `panels.py`, `background.py`, `animation.py`: visual system.
- `font_catalog.py`: browser coordinator; `font_widgets.py`: leaf controls.
- `google_fonts.py`: catalog model, network, licenses, caches.
- `mangohud.py`: process/config control; `preview.py`: owned native preview.
- `native/mangohud-background.patch`: source of truth for native extensions.

## Behavioral constraints

- Appearance changes update the private preview first. Only explicit Save
  configuration persists appearance to global/game profiles.
- Runtime frame limiting is a separate Apply action. Preserve game identity
  checks and global-versus-profile save selection.
- Never change numeric fields or font weights on mouse-wheel events. Open
  combo lists remain scrollable. This is an explicit user preference.
- Additional text font click copies the chosen main font; right-click retains
  local-file selection. The catalog icon chooses an independent font.
- Keep UI labels English. The user normally discusses changes in Polish.
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

Run `python3 -B -m unittest discover -s tests -q` and, for UI changes,
`QT_QPA_PLATFORM=offscreen python3 -B tests/check_ui.py`. The UI smoke uses no
network, game windows or real preference writes. See DEVELOPMENT for native
and live-download checks. Never capture unrelated desktop windows; native
capture helpers restrict themselves to the test process's owned window.

Install completed changes with `python3 -B scripts/install.py` when the user
expects the local app updated. Running Vela/games need restarting for new code
or libraries. Do not commit, squash or push unless the user requests it.
