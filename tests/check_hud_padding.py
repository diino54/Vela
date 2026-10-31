"""Pixel regression for padding, content size and screen anchors.

Opens only a disposable test window; captures its own X11 pixmap by process ID.
Usage: python3 tests/check_hud_padding.py --backend opengl --output /tmp/padding-gl
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
from native_capture import capture


def measurements(path):
    with Image.open(path) as image:
        image = image.convert('RGB')
        r, g, b = image.split()
        red = ImageChops.subtract(r, g).point(lambda v: 255 if v > 30 else 0)
        blue = ImageChops.subtract(b, g).point(lambda v: 255 if v > 30 else 0)
        panel = ImageChops.multiply(red, blue).getbbox()
        if not panel:
            raise AssertionError('Panel not found')
        channels = image.crop(panel).split()
        white = channels[0].point(lambda v: 255 if v > 230 else 0)
        for channel in channels[1:]:
            white = ImageChops.multiply(white, channel.point(lambda v: 255 if v > 230 else 0))
        text = white.getbbox()
        if not text:
            raise AssertionError('Text not found')
        return panel, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('opengl', 'vulkan'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='vela-padding-test-') as directory:
        directory = Path(directory)
        config = directory / 'hud.conf'
        config.write_text('fps_limit=60\n')
        env = runtime.environment(directory)
        env.update(MANGOHUD_CONFIGFILE=str(config), DISABLE_LSFGVK='1', QT_QPA_PLATFORM='xcb')
        env.pop('MANGOHUD_CONFIG', None)
        env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
        command = ([sys.executable, '-B', '-m', 'vela.scene'] if args.backend == 'opengl'
                   else ['vkcube', '--c', '4000', '--wsi', 'xcb', '--width', '800', '--height', '450'])
        with (args.output / 'renderer.log').open('w') as log:
            child = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            try:
                time.sleep(2)
                assert child.poll() is None
                for position in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
                    base = (f'position={position}\nwidth=360\nbackground_color=CC00CC\nbackground_alpha=1\n'
                            'legacy_layout=0\nround_corners=0\nfont_size=48\nfont_size_secondary=48\ntext_color=FFFFFF\ntext_outline=0\n'
                            'fps=0\nframetime=0\nframe_timing=0\ngpu_stats=0\ncpu_stats=0\ncustom_text=TEST\n')
                    previous = None
                    for padding in (0, 5, 20, 40, 64):
                        content = mangohud.managed_content(base, 60, 'early', True, {'vela_padding': padding})
                        mangohud.replace_watched(config, content.encode())
                        time.sleep(.7)
                        target = args.output / f'{position}-{padding}.png'
                        capture(child.pid, target)
                        panel, text = measurements(target)
                        anchor = (panel[0] if position.endswith('left') else panel[2],
                                  panel[1] if position.startswith('top') else panel[3])
                        size = (panel[2]-panel[0], panel[3]-panel[1])
                        text_size = (text[2]-text[0], text[3]-text[1])
                        results.append(dict(position=position, padding=padding, anchor=anchor,
                                            size=size, inset=text[:2], text_size=text_size))
                        print(results[-1], flush=True)
                        if previous is not None:
                            delta = padding - previous['padding']
                            for a, b in zip(anchor, previous['anchor']):
                                assert abs(a-b) <= 1, ('anchor', previous, results[-1])
                            for a, b in zip(size, previous['size']):
                                assert abs(a-b-2*delta) <= 1, ('panel size', previous, results[-1])
                            for a, b in zip(text[:2], previous['inset']):
                                assert abs(a-b-delta) <= 1, ('inset', previous, results[-1])
                            assert text_size == previous['text_size'], ('text size', previous, results[-1])
                        previous = results[-1]
            finally:
                child.terminate()
                child.wait(timeout=5)
                (args.output / 'measurements.json').write_text(json.dumps(results, indent=2))
    print('PASS: content inset, content size and all four anchors', flush=True)


if __name__ == '__main__':
    main()
