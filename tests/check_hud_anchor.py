"""Opt-in pixel regression for the native HUD anchor (opens a test window).

Run: python3 tests/check_hud_anchor.py --backend opengl --output /tmp/vela-anchor-gl
Requires the private runtime, Pillow, KDE Spectacle, and a graphical session.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vela import mangohud, runtime


def panel_bounds(path):
    with Image.open(path) as image:
        r, g, b = image.convert('RGB').split()
        red = ImageChops.subtract(r, g).point(lambda v: 255 if v > 30 else 0)
        blue = ImageChops.subtract(b, g).point(lambda v: 255 if v > 30 else 0)
        neutral = ImageChops.difference(r, b).point(lambda v: 255 if v < 30 else 0)
        bounds = ImageChops.multiply(ImageChops.multiply(red, blue), neutral).getbbox()
        if bounds is None:
            raise AssertionError('Test HUD not visible in capture; check active window.')
        return bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('opengl', 'vulkan'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='vela-anchor-') as directory:
        directory = Path(directory)
        config = directory / 'hud.conf'
        config.write_text('fps_limit=60\nbackground_color=CC00CC\nbackground_alpha=1\nwidth=360\n')
        env = runtime.environment(directory)
        env.update(MANGOHUD_CONFIGFILE=str(config), DISABLE_LSFGVK='1', QT_QPA_PLATFORM='xcb')
        env.pop('MANGOHUD_CONFIG', None)
        env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
        if args.backend == 'opengl':
            command = [sys.executable, '-B', '-m', 'vela.scene']
        else:
            command = ['vkcube', '--c', '4000', '--wsi', 'xcb', '--width', '800', '--height', '450']
        with (args.output / 'renderer.log').open('w') as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            try:
                time.sleep(2)
                assert process.poll() is None, 'Renderer did not start; see renderer.log'
                for position in ('top-left', 'top-right'):
                    base = f'position={position}\nwidth=360\nbackground_color=CC00CC\nbackground_alpha=1\nround_corners=12\n'
                    options = {'vela_border_color': 'CC00CC', 'vela_border_width': 0}
                    changes = [
                        ('baseline', {}),
                        ('shadow', {'vela_shadow_alpha': .7}),
                        ('softness', {'vela_shadow_blur': 40}),
                        ('offset', {'vela_shadow_offset_x': -30, 'vela_shadow_offset_y': 24}),
                        ('opacity', {'vela_shadow_alpha': .2}),
                        ('noise', {'vela_background_noise': .3}),
                        ('border', {'vela_border_width': 5}),
                        ('font', {'font_size': 28}),
                        ('text', {'text_color': 'AAFFFF', 'alpha': .5}),
                        ('background', {'background_alpha': .5}),
                        ('metrics', {'gpu_temp': 1, 'ram': 1}),
                        ('corners', {'round_corners': 24}),
                    ]
                    anchor = None
                    for name, values in changes:
                        options.update(values)
                        mangohud.replace_watched(config, mangohud.managed_content(base, 60, 'early', True, options).encode())
                        time.sleep(.7)
                        screenshot = args.output / f'{position}-{name}.png'
                        subprocess.run(['spectacle', '-b', '-n', '-a', '-e', '-S', '-o', str(screenshot)],
                                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        try:
                            bounds = panel_bounds(screenshot)
                        except AssertionError:
                            screenshot.unlink(missing_ok=True)
                            raise
                        current = (bounds[0] if position == 'top-left' else bounds[2], bounds[1])
                        if anchor is None:
                            anchor = current
                        results.append({'position': position, 'setting': name, 'anchor': current, 'bounds': bounds})
                        print(position, name, current, flush=True)
                        assert all(abs(a-b) <= 1 for a, b in zip(current, anchor)), (name, anchor, current)
            finally:
                process.terminate()
                process.wait(timeout=5)
                (args.output / 'anchors.json').write_text(json.dumps(results, indent=2))
    print('PASS: all appearance changes preserve both HUD anchors', flush=True)


if __name__ == '__main__':
    main()
