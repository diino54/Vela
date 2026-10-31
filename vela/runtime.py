"""Opt-in launcher for the private, textured MangoHud build (64-bit Linux)."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile


def library_directory():
    return Path(__file__).resolve().parent / 'native' / platform.machine()


def available():
    return all((library_directory() / name).is_file() for name in
               ('libMangoHud.so', 'libMangoHud_opengl.so', 'libMangoHud_shim.so'))


def environment(directory, base=None):
    """Create a process-private explicit Vulkan manifest; keep other layers."""
    if not available():
        raise RuntimeError('Vela MangoHud is not built. Run scripts/build_mangohud.py first.')
    libraries = library_directory()
    name = f'VK_LAYER_VELA_MANGOHUD_overlay_{platform.machine()}'
    manifest = {
        'file_format_version': '1.0.0',
        'layer': {
            'name': name, 'type': 'GLOBAL', 'api_version': '1.3.0',
            'library_path': str(libraries / 'libMangoHud.so'),
            'implementation_version': '1', 'description': 'Vela textured MangoHud',
            'functions': {'vkGetInstanceProcAddr': 'overlay_GetInstanceProcAddr',
                          'vkGetDeviceProcAddr': 'overlay_GetDeviceProcAddr'},
        },
    }
    (Path(directory) / 'Vela-MangoHud.json').write_text(json.dumps(manifest))
    env = dict(os.environ if base is None else base)
    # Disable only the stock implicit MangoHud layer. Ours is explicitly enabled.
    env.update(MANGOHUD='1', DISABLE_MANGOHUD='1',
               MANGOHUD_OPENGL_LIBS=str(libraries / 'libMangoHud_opengl.so'))
    env['VK_ADD_LAYER_PATH'] = str(directory) + (os.pathsep + env['VK_ADD_LAYER_PATH'] if env.get('VK_ADD_LAYER_PATH') else '')
    layers = [v for v in env.get('VK_INSTANCE_LAYERS', '').split(':') if v and 'MANGOHUD_overlay_' not in v]
    env['VK_INSTANCE_LAYERS'] = ':'.join(layers + [name])
    preload = env.get('LD_PRELOAD', '').replace(':', ' ').split()
    preload = [v for v in preload if 'libMangoHud' not in Path(v).name]
    env['LD_PRELOAD'] = ' '.join([str(libraries / 'libMangoHud_shim.so')] + preload)
    return env


def main():
    parser = argparse.ArgumentParser(description='Launch a 64-bit application with Vela textured MangoHud.')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        parser.error('Provide an application command after --.')
    with tempfile.TemporaryDirectory(prefix='vela-layer-') as directory:
        try:
            return subprocess.call(command, env=environment(directory))
        except (OSError, RuntimeError) as error:
            parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
