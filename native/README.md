# Experimental MangoHud backgrounds

Vela adds subtle noise, a configurable HUD border, a soft drop shadow and
experimental GPU backdrop blur.
The preview automatically uses the private build when it is present. All effects default to off. Frosted Grid has been removed; old configurations are
accepted without rendering that effect, and Vela removes its key when saving.
Optional backdrop blur samples the game image before the HUD is drawn. Text
remains sharp.

The extension is a patch against MangoHud v0.8.2, commit
`a37b007e8018738270c9282c3a53b0ed7e786bcf`. The system package is not replaced.
The build also includes an explicit `<sstream>` include needed with GCC 16.

## Build

On Fedora 44, use an isolated Podman container:

```sh
python3 scripts/build_mangohud.py --container
```

Alternatively, install the dependencies listed in the build script in your
build environment and run it without `--container`. The output goes into
`vela/native/x86_64/`, with third-party notices. Restart Vela after building.
Controls are disabled if the runtime is missing.

## Try it

Run from the repository:

```sh
python3 -m vela.ui
```

The appearance controls update only the private preview until Save configuration
is pressed. Save the desired global or game configuration before testing a game.

An application already using stock MangoHud cannot acquire the new renderer
while running. Start it through the opt-in launcher instead:

```sh
python3 -m vela.runtime -- /absolute/path/to/game
```

After `python3 scripts/install.py`, the user install also contains a
`vela-mangohud` launcher. Steam launch options for a directly accessible game:

```text
/home/YOUR_USER/.local/bin/vela-mangohud %command%
```

Do not prepend another `mangohud` command. The launcher disables the stock
implicit Vulkan MangoHud layer for that process, adds a private explicit layer,
and preloads the private OpenGL shim. Other named Vulkan layers are retained.
It does not install a global Vulkan manifest. The temporary layer manifest is
removed when the launched command exits.

## Scope and limitations

This initial build targets 64-bit Linux on Fedora 44. OpenGL and Vulkan use the
same alpha-texture drawing code. 32-bit games, Steam pressure-vessel/Flatpak,
HDR rendering and interaction with LSFG layer ordering need separate validation.
A containerized game may not see the host runtime paths. Do not assume that the
existing LSFG fix orders the separately named experimental layer correctly.

The noise setting is `vela_background_noise=0..1`. Stock MangoHud does not
implement the Vela extension keys. Defaults are omitted when there is nothing
to override; changing an existing effect to zero writes an explicit override.
With background opacity zero, noise is hidden. Border and shadow opacity are
independent of background opacity.

The noise uses separate light and dark deterministic alpha tiles baked into the
existing font atlas once. Each tile has a maximum alpha of 31/255, with a
distribution concentrated near zero. The 0–100% control changes the opacity of
this low-contrast texture, rather than introducing full-contrast white speckles.
The tiles are drawn behind the text. Set noise to zero to disable it. To return
to the stock renderer, start the game without `vela-mangohud`.

## HUD border

The Simple panel now contains a Border section:

- Color: RGB border color (default #414141).
- Border width: 0–8 px, in 0.1 px steps; zero disables the border.
- Border opacity: 0–100%, independent of the background opacity.

The border follows Background's corner radius and stays inside the HUD bounds.
Thick borders reserve enough content padding to keep the text clear. A fully
transparent background can still have a visible border. The border defaults to
off, so existing configurations keep their previous appearance.

Keys: `vela_border_color=RRGGBB`, `vela_border_width=0..8`,
`vela_border_alpha=0..1`. Like the background textures, these settings require
the updated Vela MangoHud renderer and a restart of an already-running game.

## HUD shadow

Simple → Shadow provides:

- Color: RGB, default black.
- Shadow opacity: 0–100%; zero disables it.
- Softness: 0–40 px; zero gives a hard edge, default 16 px.
- Horizontal/vertical offset: -40–40 px; defaults 0 / 4 px.

Try opacity 40–60%, softness 16–24 px and a vertical offset of 4–8 px.
The shadow follows the panel's corner radius and is drawn behind it with a
viewport-wide clip. The panel interior is knocked out of the shadow texture,
so a transparent HUD does not acquire an opaque fill. Shadow appearance does not change HUD position or margins. At the physical
screen edge the shadow can be clipped; use explicit HUD offsets if more space
is desired.

A rounded shadow is baked into the alpha-only font atlas and drawn as nine
image patches. Softness, offsets and corner radius rebuild the baked texture
when configuration changes. Changing color or opacity only changes the tint.
There is no game-frame readback or per-frame blur pass. Shadow image drawing
still has a cost; no performance guarantee is implied.

Keys: `vela_shadow_color=RRGGBB`, `vela_shadow_alpha=0..1`,
`vela_shadow_blur=0..40`, `vela_shadow_offset_x=-40..40`,
`vela_shadow_offset_y=-40..40`.

## HUD padding

Simple → Background → Padding sets equal inner spacing on all sides, 0–64 px.
The default is 5 px. Normal HUD panels expand by twice the padding change,
preserving the content width and font size instead of squeezing the metrics.
Their selected screen anchor stays fixed. A full-width horizontal HUD keeps its
viewport width. Thick borders retain a safe minimum inset; ImGui also enforces
its minimum window size for very small HUD layouts.

Key: `vela_padding=0..64`. The setting is saved with the selected appearance
configuration and requires the updated Vela MangoHud renderer. Restart Vela and
applications using the earlier renderer after updating.

## Experimental real backdrop blur

Simple → Background → Background blur controls the sampling radius, 0–32 px.
Zero disables the effect and its scene capture. Try 8–16 px with Background
opacity at 30–60%; an opaque background hides the blurred image underneath.
Save configuration before starting a game through vela-mangohud.

This is a real current-frame GPU copy, not a frosted texture. Only the panel
region plus a sampling margin is copied, reduced to quarter width/height, then
filtered with a 9×9 binomial Gaussian approximation. Rounded masking, tint,
noise, text and border are composited separately. There is no CPU readback or
screenshot file in the runtime rendering path. Default settings leave blur off.

Desktop OpenGL 3+ resolves the region (including multisample sources), then
downsamples it into private framebuffer textures. Texture, framebuffer, unpack,
sRGB and renderer state are restored. OpenGL ES, older GL and gl_dont_flip=1
leave blur disabled. The implementation is currently intended for 8-bit SDR.

Vulkan negotiates TRANSFER_SRC usage when the surface and image format permit
it, then captures before the overlay render pass. Each in-flight overlay draw
has its own capture image, protected by its existing fence. Transfer waits,
image layouts and read/write dependencies are explicit. Capture images are
reused across frames and recreated only when their region size changes.

Vulkan blur is currently limited to filterable/copyable 8-bit RGBA/BGRA and packed 10-bit RGB SDR
swapchains with standard presentation modes and the same graphics/present queue
family. HDR, unusual surface formats and separate queue families fall back to
the ordinary HUD and emit a diagnostic. This is a prototype; game-specific
compatibility and GPU cost have not been broadly benchmarked.

Tests/check_hud_blur.py verifies a static checkerboard loses detail only under
the panel, uniform colors stay stable, HUD glyph cores remain sharp, and off
restores the original frame. tests/blur_checker_gl.py includes an MSAA fixture;
tests/blur_checker_vulkan.cpp is the matching shader-free Vulkan fixture.
The latter can be compiled in the build container with Vulkan/XCB development
headers. Optional Khronos synchronization validation is supported by the test.

## HDR color stability

V10 resolves HUD colors from the presented swapchain's format/color space and
the current configuration snapshot. Surface transfer functions are applied to
a private copy; they no longer mutate the shared instance configuration. The
palette is refreshed on context changes, configuration replacement and explicit
style invalidation. This addresses stale color state across HDR/SDR surfaces
and settings reloads. HDR backdrop blur remains unsupported.

After applying the native patch, run the cache regression with:

```sh
c++ -std=c++17 -I /path/to/MangoHud native/color_state_test.cpp -o /tmp/vela-color-state-test
/tmp/vela-color-state-test
```
