# Generated preview background

Asset: `vela/assets/preview-daylight.png`. Generated 2026-10-31 with the built-in
image_gen tool (imagegen skill), then copied into the repository unchanged.
This is an original game-like image, not a screenshot from a named game.

Final prompt:

> Use case: concept-art. Asset type: background image for a desktop game's graphics/HUD preview. Generate one polished wide 16:9 landscape image, 1920x1080 or similar wide aspect ratio. An original realistic AAA open-world game scene viewed from a high bird's-eye drone camera, looking diagonally down over a small abandoned Eastern European village with weathered rooftops, a winding road, wild grass, dense forest edges and a shallow river. Clearly daytime, natural late-morning sunlight, blue sky reflected in water, lush green foliage, warm neutral buildings, realistic detailed physically based materials and crisp environmental textures. The entire frame is the game environment, convincingly real-time rendered rather than miniature or illustration. Balanced readable composition with detailed terrain across the frame, useful for evaluating a transparent HUD against light and dark surfaces. No HUD, no text, no menus, no logos, no watermark, no black borders. No cube or foreground graphical overlays.

Integration: `scene.py` decodes the bundled image with Qt, flips scanlines for
OpenGL UV orientation, and uploads an RGB texture once on initialization.
`Preview.set_background` writes only its owned temporary control file. The
menu selection persists under the `preview_background` QSettings key.

Validation: real OpenGL process switched frosted → daylight → frosted without
restart; the final paused scene matched its initial frame exactly.

## Night variant

Asset: `vela/assets/preview-night.png`. Created with the built-in image_gen
edit tool from the daylight image, preserving the same scene composition.

Final edit prompt:

> Edit target: the supplied daytime aerial game-like village landscape. Create a NIGHT version of this exact same image for a desktop HUD preview background. Preserve the camera position, wide 16:9 framing, all architecture, bridge, river, terrain, vegetation and mountain silhouettes exactly. Change only time of day and lighting: deep blue nighttime sky with subtle stars and soft moonlight, cool readable illumination on rooftops, trees, mountains and water; a few restrained warm window lights where existing buildings have windows. Convincing realistic AAA game night rendering, enough environmental detail in the shadows to evaluate a HUD; dark but not crushed black. Keep natural contrast with highlights on river reflections. No new buildings, people, UI, text, logos or watermark. Preserve original image composition and aspect ratio.

The menu offers `Night · aerial view`, key `night`. Day/night share the same
scene control channel and one-time texture upload; neither draws the cube.
