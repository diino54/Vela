# Vela UI/UX philosophy and contribution contract

This is the rationale and extension guide for contributors and coding agents.
[UI_DESIGN.md](UI_DESIGN.md) records implemented geometry, colors and timing;
[ARCHITECTURE.md](ARCHITECTURE.md) maps code ownership;
[DEVELOPMENT.md](DEVELOPMENT.md) defines verification.

Current behavior is distinguished from contribution requirements. Accessibility
recommendations below are standards for new work, not a claim that every existing
control already meets them. Proposed HDR tools are not implemented features;
check [STATE.md](STATE.md) before describing product capabilities.

## 1. Product intent

Vela makes technical overlay configuration approachable while retaining precise
control. The preview is the working surface: users see appearance changes before
choosing where to save them. Correct file ownership, process identity and native
rendering are part of the experience, not details to discard during visual cleanup.

The direction is quiet, dark and tactile: charcoal surfaces, subtle frosted
texture, restrained blue accents, rounded corners, readable typography and smooth
motion. Information and actions must remain understandable without animation.

Priorities, in order:

1. Preserve user files, unsaved edits and correct game/profile targeting.
2. Keep input responsive and represent actual state truthfully.
3. Explain configuration through grouping, preview and clear feedback.
4. Maintain the established material, hierarchy and motion.
5. Add decoration only when it supports those priorities.

## 2. Shared aesthetics, separate renderers

| Surface | Implementation | Scope |
| --- | --- | --- |
| Desktop controls/modals | PySide6, QSS, QPainter | Vela itself |
| Embedded preview | Owned OpenGL scene and private MangoHud configuration | Preview instance |
| Game HUD | Private MangoHud GL/Vulkan libraries | Games launched through the private runtime |
| ReShade overlay | Modified ReShade, ImGui, GPU shaders | Games with that runtime installed |

These systems do not share CSS, font units or rendering code. Qt's frosted material
is a cached procedural texture, not live desktop blur. ReShade has a separate GPU
backdrop; MangoHud has another blur path with different limitations. A desktop
style edit cannot automatically change a game. Keep foreground text sharp and
transient opacity independent from saved configuration values.

## 3. Material and color

The background establishes depth without competing with controls. Preserve the
dark radial gradient and faint fading grid. Frosted panels should read as nearly
black matte glass, with restrained texture and thin borders. Avoid visible sand,
bright glass, large colorful halos and decorative gradients inside inputs.

| Role | Desktop reference | Use |
| --- | --- | --- |
| Root | #090909 to #121212 | Gradient and faint grid |
| Panel | FrostedPanel; #303030 border | Main columns/modal shell |
| Card | #202020; #303030 border | Families, diagnostics and setting groups |
| Input | #111111; #2c2c2c border | Editable values/selectors |
| Neutral button | #333333 | Secondary action |
| Primary action | #246bce; white text | Save, Apply, Continue |
| Body text | #dddddd | Normal labels |
| Strong text | #eeeeee / #f2f2f2 | Headings/prominent values |
| Metadata | #909090 in fontMeta | Supporting information |
| Line icons | #9fbce3 | Shared metric icon language |
| Invalid field | FieldGlow RGB 230/80/85 | Missing/invalid input after an attempt |

These are references, not a duplicated token implementation. `theme.py`,
`panels.py`, `animation.py` and the owning widget define exact states and alpha.
Qt palette fallback colors differ from some QSS colors; do not normalize blindly.

Desktop typography uses Noto Sans: 13 px body, 15 px semibold panel titles,
12 px semibold section titles. Metric values use 17 px semibold. Supporting text
must remain readable. Invalid-field text becomes brighter against the red tint.
Prefer short labels and supporting sentences over technical paragraphs per input.

Radii follow hierarchy: inputs around 5 px, buttons 7 px, cards 9 px, modal shell
12 px. Main FrostedPanel defaults to 6 px. Reuse the appropriate component rather
than forcing every surface to one radius. ReShade uses separate font/style units.

## 4. Space, grouping and cards

The main screen keeps customization left, expanding preview center and
process/limiter/experimental controls right. New controls must not consume the
preview. Simple holds standard MangoHud options; Advanced holds Vela's MangoHud
extensions. Application paths and configuration inspection belong in Settings.

Use centered, bounded inset modals with the owner visible and dimmed behind them.
Size for the task: an entry/completion screen must not retain a large empty wizard
panel. [UI_DESIGN.md](UI_DESIGN.md) lists implemented maximum sizes and rails.
These are upper bounds, constrained by the owner, not mandatory fixed dimensions.

| Card kind | Interaction |
| --- | --- |
| Navigation | Whole tile clickable, clear destination |
| Read-only metric | Icon, label, prominent selectable value; no fake button behavior |
| Editable setting | Label and real input in the same card |
| Review | Summarize selected values before an explicit operation |

Use line SVG icons from the shared system, not emoji or unrelated icon styles.
Icon-only actions need tooltips and accessible names. Folder opens a directory,
pen opens configuration, trash begins removal review. It never deletes directly.

Existing cards use roughly 16/14 px padding and 12 px gaps; modal content generally
uses 20 px padding. These are reusable references, not a universal spacing scale.
Long paths/names must wrap, elide with access to the full value, or scroll without
stretching the dialog. Keep primary footer actions reachable.

## 5. Editing, preview and saving

Appearance edits update only the private preview until Save configuration.
The preview caption identifies the loaded configuration. Switching processes
with unsaved changes offers Save and switch / Discard and switch / Cancel.
Save targets the original loaded file, never a newly selected destination by
accident. Failed saves retain the edit buffer and allow recovery.

Frame-limit Apply is a separate live operation. Do not attach appearance saves
to it. ReShade Configure likewise has a loaded snapshot, dirty buffer and explicit
Save changes. Searching/filtering cards must not dirty or save anything. External
INI changes block a stale save.

| State | Persistence contract |
| --- | --- |
| Window preferences, collapsed sections, preview background | QSettings; immediate preference persistence is allowed |
| Appearance edits | Preview buffer, then explicit global/game save |
| Frame limit | Separate live Apply workflow |
| ReShade settings | Existing game-local INI, explicit conflict-checked save |
| Installer choices | Temporary session; reset on close |
| Fonts/licenses | Vela-managed data/cache directories |
| HDR diagnostics | Read-only snapshot, explicit refresh |

Do not infer that every modal resets or that every setting autosaves. Preserve
the specific workflow's ownership and lifetime.

## 6. Input rules

Mouse-wheel events must not alter numbers, font weights or the alpha slider.
Scrolling a page across an input must be safe. Open combo lists may scroll;
that differs from changing a closed combo's value with the wheel. Reuse existing
wheel-safe controls and the minus/plus pattern. Hide native spin arrows where
editable cards already use the shared pattern.

Both font fields open a local chooser on left-click; catalog icons browse Google
Fonts. Identical files, including aliases, normalize the additional font to Same
as main font. Do not restore the old additional-font context menu.

Collapsing groups preserves their values. Still preview images dim/disable Pause
animation while retaining its previous selection. Disabled actions must retain
understandable prerequisites; do not create unexplained dead-looking controls.

## 7. Motion and feedback

Motion is intentional and must survive refactors. Use fades, small offsets and
subtle painted feedback. Avoid bouncing, dramatic zoom and flashing. Feedback
must not change hit regions, HUD anchors, saved font sizes or layout measurements.

| Interaction | Implemented reference |
| --- | --- |
| Modal opening/closing | 400/260 ms, OutCubic, cached proxy |
| Font category marker | 340 ms |
| Font grid change | 320 ms fade/slide |
| Font tile reveal | 420 ms each, 65 ms stagger in reading order |
| ReShade step content | 280 ms fade |
| Available primary action | Soft 2400 ms looping blue ButtonGlow |
| Invalid attempt | One 1100 ms FieldGlow pulse, then quiet static error |

Invalid-state sequence: a failed attempt triggers one gentle pulse from .45 to
.75 intensity and back to .45. A subtle red border and tinted background remain;
text/placeholder stay bright and the halo stops. Another failed attempt retriggers
it. Correction restores the original style/colors. Checkboxes, confirmation cards
and inputs share this language. Do not use a permanent fast red pulse or red text
alone. A missing-input primary action is softly dimmed but clickable so it can
highlight missing fields. This does not apply to actions blocked by an active job.

Animate cached modal imagery rather than scaling live controls. Cancel/invalidate
queued reveals when closing, paging or reopening. Font loading must remain staged
and bounded. Native ReShade fades have their own controls; do not substitute Qt
timings or save transient alpha into persistent style settings.

## 8. Modal lifecycle and responsiveness

The native GL child can stack above ordinary Qt widgets. Modal handling snapshots
only Vela's owned surface, hides the live preview and dims the cached image.
Restore prior visibility and background enabled state on exit, including animation
interruption, resize, reopening and shutdown. Use FrostedModal rather than copying
only its appearance. The font browser has its own established coordinator.

Network, library scanning and installation/removal must not block the GUI thread.
Use bounded requests, queued signals and staged widget creation. Retain workers
until finished. Closing/resetting a wizard does not abandon active file work;
late completion must not navigate a reset screen to Ready.

Delayed callbacks must check generation, target and lifetime. Do not repair races
with arbitrary sleeps or nested processEvents loops. Loading must resolve to
success, actionable failure or bounded fallback. Preserve diagnostic messages
for operational failures instead of presenting them as missing input.

## 9. Honest diagnostics and safe operations

Missing data is Unknown, not Disabled, zero or success. Desktop HDR state is not
proof of game HDR output, monitor calibration or PQ/scRGB correctness. Keep source
and scope visible where they affect interpretation. Current HDR diagnostics are
read-only; future launch/calibration helpers must not be documented as available.

Installation must not silently overwrite another hook/mod or existing config.
A hook alone is not proof of Vela ownership. `.vela-reshade.json` is an inventory,
not user settings. Removal validates scope and requires separate confirmation.
Ordinary removal preserves modifications; complete removal exposes the broader
file list first. Keep the explicit game-closed confirmation. Do not add extra
confirmation dialogs to ordinary reversible editing.

## 10. How to extend the interface

Before adding a setting, identify its owner: standard MangoHud, private MangoHud,
application preference, ReShade INI or read-only diagnostic. Define units, range,
default, loaded state, dirty state, save target and failure behavior. Reuse shared
controls/cards and connect to the existing state owner. Layout builders must not
create competing persistence models.

Before adding a screen, define compact bounds, scrolling, Back/Close/Escape,
worker ownership and reset rules. Before adding motion, define its trigger,
endpoint, interruption and cleanup. Preserve hierarchy without motion.

For new controls, provide keyboard focus, accessible names and text equivalents
for color-coded states. Check keyboard traversal and visible focus. Do not claim
a general reduced-motion mode, universal accessibility or contrast certification
unless implemented and verified.

## 11. Acceptance review

Inspect normal, hover, focus, unavailable, dirty, invalid, loading and failure
states where applicable. Try long names/paths, small owner dimensions, high-DPI
scaling, wheel input, rapid navigation and closing during work.

Owned offscreen screenshots verify Qt layout. They do not verify GL stacking,
XWayland style propagation, game blur, HDR conversion or Alt-Tab. Use the matching
owned native harness or identify a manual game test explicitly. Report actual
evidence and remaining limits. A successful change preserves predictable saves,
readable controls, restrained materials and responsive motion.
