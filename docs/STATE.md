# Current implementation state

Recorded 2026-10-31. Update this when completing a material feature or changing
a known limitation; use Git history/diffs for the exact current file state.

## Implemented and verified

- Private MangoHud extension: subtle noise, customizable border/shadow,
  internal padding and real GPU backdrop blur on supported desktop GL/Vulkan.
- Shadow changes no longer move the HUD anchor. Padding was checked at all
  four corners in both backends.
- 8-bit and packed 10-bit SDR blur; the user confirmed it works in Stalker 2
  after the 10-bit compatibility fix. HDR blur remains disabled.
- V10 surface-specific HDR color state; the user confirmed the HDR Alt-Tab
  appearance problem was fixed after restarting with the new library.
- Full Google Fonts metadata integration, categories/search/sorting/paging,
  weight/italic TTF downloads and licenses, bounded lazy specimens and caches.
- Inset frosted font modal with dimmed background, loading cover and staggered
  downward/fade tile reveals; scroll cannot change font weights.
- Additional font click copies main; catalog/right-click choose alternatives.

## Important limitations and non-features

- HDR blur is not implemented. HDR color conversion of the HUD is separate.
- Blur fallback applies to unsupported formats, GLES/older GL and unsupported
  Vulkan graphics/present arrangements. See native docs for exact checks.
- Google catalog/manifest endpoints used by the website may change; bundled
  metadata and local caches are the fallback. No API key is required.
- CSS-based game HUD themes were discussed but never implemented. Do not
  document theme.css as a supported feature.
- Frosted Grid was removed from the game HUD. The Qt frosted panel material
  is intentionally still present; do not confuse them.

## Refactor checkpoints

- Window entry point stays `vela.ui.Window` / `python -m vela.ui`.
- Main actions remain in ui.py; builders, controls, theme and font leaf widgets
  now live in separate modules (see ARCHITECTURE). No native rebuild was
  needed for this Python-only refactor. Existing V10 native changes were
  preserved as part of the working tree.
- Main-window and font-modal static pixels were identical before and after
  extraction (loop animations frozen, text-caret blink excluded). Unit and offscreen integration checks passed.
- Old Dropbox checkout is gone. Repository is the GitHub working copy.
- No commit, history rewrite or push is part of this refactor.
