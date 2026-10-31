# Validation — 2026-10-29

- Five unittest cases passed: effect roundtrip/off state, idempotence, stock
  defaults, invalid input, inode/limiter preservation, launcher environment.
- Qt offscreen smoke passed: window construction, enabled effect controls,
  12% -> 0.12 conversion, preview updates and shutdown.
- Both shared renderers compiled in Fedora 44 with GCC 16.2.1.
- Checked the patch in reverse against the modified pinned source tree.
- Real XWayland/OpenGL preview used the private libMangoHud_opengl.so, verified
  in /proc/PID/maps. Captured plain, noise 12%, combined frost/noise and off.
  Scene startup and shutdown passed, with no output in scene.log.
- Vulkan vkcube rendered 240 frames and exited 0. Verified the private
  libMangoHud.so was mapped and the stock Vulkan MangoHud library was absent.
  Captured the rendered textured HUD. Existing LSFG and DZN driver diagnostics
  appeared in the loader log; this test does not validate LSFG interoperability.
- The user installation was updated through scripts/install.py.

No game, 32-bit process, HDR or Steam container test was performed. The GPU cost
has not been benchmarked. Screenshots are in the chat's visualizations output.

## Subtle grain revision

- Replaced full-range white grain with separate low-contrast light/dark masks
  (maximum alpha 31/255, distribution concentrated around zero).
- Noise opacity accepts fractional percentages; Qt smoke checked 0.5% -> 0.005.
- Rebuilt both renderers. OpenGL preview verified at 0%, 12% and 100%, with off
  state restored; the private library mapping was checked.
- Vulkan vkcube passed another 240-frame run with opacity 100% and exited 0.
- Existing configuration keys and numeric values remain compatible.
- Installer copies atomically to avoid truncating a library mapped by a running
  preview. Running applications keep the old renderer until restarted.

## Diffuse frost revision

Removed periodic grid components from the frost atlas texture; only the smooth
radial luminance envelope remains. Both renderers rebuilt successfully. Real
OpenGL preview checked with frost enabled and noise at zero, followed by off;
no grid lines remain in the captured HUD. No actual game-image blur is applied.

## Custom border revision

Seven unittest cases passed, including border roundtrip, disabling, defaults and
invalid values. Qt smoke checked width, percent conversion, color and preview
configuration. Real OpenGL screenshots checked a 1 px / 60% blue border, an 8 px
orange border with extra text padding, a border over a fully transparent
background, and off. The native OpenGL library mapping was verified. Vulkan
vkcube rendered the blue border for 240 frames and exited 0. Both renderers and
the local installation were updated. The default border is off.

## Shadow and retired Frosted Grid

Eight unittest cases passed, including shadow roundtrip, signed offsets,
validation, default omission and removal of retired frost keys. Qt smoke
verified shadow controls, opacity conversion and absence of Frosted Grid.
Both native renderers rebuilt. Real OpenGL preview checked black soft shadow,
colored soft shadow, signed offset, zero-softness hard shadow, transparent
background, and off. Changes in shape rebuilt the atlas live without restarting
the preview; private library mapping and cleanup were checked. Vulkan vkcube
rendered a colored shadow for 240 frames and exited 0. Shadow is drawn behind
the panel, outside its clip, with an interior knockout and automatic margins.
The retired frost setting remains accepted as an ignored legacy parser key;
it has no renderer and Vela removes active entries from configurations on save.
No game-frame blur was added. The local installation was updated.

## Stable HUD anchor regression

Removed the shadow-dependent margin from position_layer. Appearance changes now
keep stock MangoHud positioning; shadows may be clipped at physical screen
edges instead of moving the panel. Explicit position and offsets are preserved.

Before the fix, the pixel regression reproduced a jump from (10,10) to (22,22)
when enabling the shadow. After the fix, all 24 OpenGL snapshots passed exactly:
left anchor (10,10), right anchor (790,10), through changes to shadow, softness,
offsets, opacity, noise, border, font, text, background, metrics and corners.
Vulkan passed the left-anchor baseline and shadow, softness, offset, opacity,
noise, border and font cases at (10,10). The remaining Vulkan captures were
interrupted by an active-window focus change, not a renderer error; the invalid
capture was deleted. Nine unit tests passed, including explicit positioning
preservation. The corrected native libraries and user installation were updated.

Manual pixel regression: tests/check_hud_anchor.py. It opens its own graphical
window, which must remain active during screenshot capture.

## HUD padding — 2026-10-30

Ten unit tests passed, including padding roundtrip, zero, default omission and
invalid values. Qt smoke checked the 0/20 px control and preview binding.
Both native renderers rebuilt from the pinned upstream revision and the updated
patch. The patch was reverse-checked against the modified source tree.

The pixel regression tests/check_hud_padding.py passed 20 captures per backend
(OpenGL and Vulkan): padding 0, 5, 20, 40 and 64 px at all four screen corners.
Every pixel of added padding increased content inset by one pixel and normal
panel size by two pixels; text dimensions stayed 92x32 throughout. Anchors were
exactly (10,10), (790,10), (10,440) and (790,440) in an 800x450 test window.
The helper captures only the test process's XComposite pixmap, using _NET_WM_PID
or XRes ownership, so tests do not depend on focus or capture other apps.
The local user installation was updated. Games and Vela need restarting.

## Experimental real GPU blur — 2026-10-30

Eleven Python unit tests passed, including blur roundtrip, zero/disable and
invalid values. Qt offscreen smoke verified the new control and preview binding.
The native patch reverse-check passed against the modified pinned source.

Static checkerboard tests passed for desktop OpenGL (four-sample MSAA),
OpenGL with framebuffer sRGB enabled, and Vulkan with synchronization validation.
At radius 24, scene standard deviation fell from 76.5 to 0.0 in OpenGL and
from 76.5 to 0.49 in Vulkan. Opaque glyph cores remained sharp, uniform colors
were preserved within two levels, the scene outside the HUD stayed identical,
and disabling blur restored the original whole frame bit-for-bit. Vulkan
reported no validation errors or synchronization hazards.

Fixtures: tests/check_hud_blur.py, tests/blur_checker_gl.py and
tests/blur_checker_vulkan.cpp. Captures use the test process's own window.
This validates SDR test scenes, not S.T.A.L.K.E.R. 2 or game performance.
HDR, GLES and distinct Vulkan graphics/present queue families use the normal
HUD fallback. The local installation was updated; restart Vela and games.

## Stalker blur compatibility follow-up — 2026-10-30

The running game mapped Vela v8 correctly, with blur=32 and background alpha
0.7, but emitted the native unsupported-swapchain warning. That warning did
not distinguish format from queue-family limitations, so the exact cause
was not established. V9 logs numeric format/colorspace, capabilities, queue
families and image count, and confirms successful blur enablement as well.
Packed A2B10G10R10/A2R10G10B10 UNORM SDR is now accepted with the same
capability checks. HDR remains excluded.

Eleven Python unit tests and the native patch reverse-check passed. The
10-bit fixture explicitly reports unavailable on this X11 surface; no
10-bit rendering success is claimed. The game must restart to load v9.

V9 8-bit Vulkan pixel regression passed all five states with synchronization
validation enabled: sharp text, stable uniform colors, unchanged outside
region and bit-exact off-state restoration.

## HDR/Alt-Tab color-state fix — 2026-10-31

The game log showed A2B10G10R10 with HDR10 ST2084 (format 64, colorspace
1000104008). No running game was available during this diagnosis. Upstream
conversion mutated instance params only at swapchain creation; subsequent
color updates used instance params while HUD drawing used the published
configuration snapshot. V10 separates the surface transfer state from saved
settings and refreshes the active context palette from the latest snapshot.

Both native backends compiled. Native color-state regression passed HDR/SDR/HDR
context switches, config replacement, dirty style invalidation, no unnecessary
updates and snapshot immutability. Seventeen Python tests passed. The patch
reverse-check passed. Vulkan pixel blur regression passed all five states.
A separate live Vulkan color test passed white/red/green/white config reloads
and exact final-frame restoration. Actual HDR Alt-Tab behavior in Stalker
still requires an in-game check after restarting with the new library.
