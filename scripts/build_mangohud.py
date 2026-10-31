#!/usr/bin/env python3
"""Build the opt-in Vela MangoHud extension without replacing system packages."""
import argparse
from pathlib import Path
import platform
import os
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a37b007e8018738270c9282c3a53b0ed7e786bcf'  # MangoHud v0.8.2
OPTIONS = ['-Dwith_xnvctrl=disabled', '-Dinclude_doc=false', '-Dmangoplot=disabled', '-Dtests=disabled']
LIBRARIES = ('libMangoHud.so', 'libMangoHud_opengl.so', 'libMangoHud_shim.so')
PACKAGES = ['gcc-c++', 'meson', 'ninja-build', 'python3-mako', 'glslang', 'libX11-devel',
            'libxkbcommon-devel', 'wayland-devel', 'dbus-devel', 'libglvnd-devel', 'libstdc++-static',
            'git', 'pkgconf-pkg-config']


def run(*args, **kwargs):
    subprocess.run(list(args), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', action='store_true', help='Build in a disposable Fedora 44 Podman container.')
    parser.add_argument('-j', '--jobs', type=int, default=4)
    args = parser.parse_args()
    if platform.machine() != 'x86_64':
        parser.error('The experimental runtime is currently tested only on x86_64 Linux.')
    if args.jobs < 1:
        parser.error('--jobs must be positive.')
    with tempfile.TemporaryDirectory(prefix='vela-mangohud-build-') as temporary:
        source = Path(temporary) / 'source'
        run('git', 'clone', '--depth', '1', '--branch', 'v0.8.2',
            'https://github.com/flightlessmango/MangoHud.git', str(source))
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        if actual != REVISION:
            raise RuntimeError('Upstream tag changed; refusing to apply the patch to an unknown revision.')
        run('git', 'apply', str(ROOT / 'native/mangohud-background.patch'), cwd=source)
        if args.container:
            name = 'vela-build-' + uuid.uuid4().hex[:10]
            try:
                run('podman', 'run', '-d', '--name', name, '--network=host',
                    '-v', f'{source}:/src:Z', 'registry.fedoraproject.org/fedora:44', 'sleep', 'infinity')
                run('podman', 'exec', name, 'dnf', '-y', 'install', *PACKAGES)
                run('podman', 'exec', '-w', '/src', name, 'meson', 'setup', 'build', *OPTIONS)
                run('podman', 'exec', '-w', '/src', name, 'meson', 'compile', '-C', 'build', '-j', str(args.jobs))
            finally:
                subprocess.run(['podman', 'rm', '-f', name], check=False)
        else:
            run('meson', 'setup', 'build', *OPTIONS, cwd=source)
            run('meson', 'compile', '-C', 'build', '-j', str(args.jobs), cwd=source)
        destination = ROOT / 'vela/native' / platform.machine()
        destination.mkdir(parents=True, exist_ok=True)
        for library in LIBRARIES:
            fd, temporary_library = tempfile.mkstemp(prefix='.vela-library-', dir=destination)
            os.close(fd)
            try:
                shutil.copy2(source / 'build/src' / library, temporary_library)
                os.replace(temporary_library, destination / library)
            finally:
                Path(temporary_library).unlink(missing_ok=True)
        notices = [f'MangoHud {REVISION}\n', (source / 'LICENSE').read_text()]
        for directory in sorted((source / 'subprojects').iterdir()):
            if directory.is_dir():
                for license_file in sorted(directory.glob('*LICENSE*')) + sorted(directory.glob('*COPYING*')):
                    if license_file.is_file():
                        notices.extend([f'\n\n{directory.name}/{license_file.name}\n', license_file.read_text(errors='replace')])
        (destination / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices))
        (destination / 'BUILD.txt').write_text(f'MangoHud {REVISION}\nVela background patch v9 (10-bit SDR blur and diagnostics)\nFedora 44 x86_64 experimental build\n')
        print(f'Built Vela MangoHud in {destination}. Restart Vela to use it.')


if __name__ == '__main__':
    main()
