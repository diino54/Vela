#!/usr/bin/env python3
"""Install the MangoHud controller in user directories; install Vela."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
home = Path.home()
data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
destination = data / 'vela'
bin_dir = home / '.local/bin'
desktop = data / 'applications/vela.desktop'
parser = argparse.ArgumentParser()
parser.add_argument('--uninstall', action='store_true')
args = parser.parse_args()

if args.uninstall:
    sys.path.insert(0, str(root))
    from vela import layer_order
    config = layer_order.settings_path()
    if config.exists():
        try:
            layer_order.remove()
        except ValueError:
            pass  # Another tool owns this configuration.
    for path in (desktop, bin_dir / 'vela', bin_dir / 'vela-mangohud'):
        path.unlink(missing_ok=True)
    if destination.exists():
        shutil.rmtree(destination)
    print('Vela uninstalled. MangoHud profiles have been kept.')
    sys.exit(0)
if not shutil.which('mangohud'):
    sys.exit('MangoHud is missing. Install it with: sudo dnf install mangohud python3-pyside6')
if sys.version_info < (3, 11):
    sys.exit('Vela requires Python 3.11 or newer.')
try:
    import PySide6
    from PySide6 import QtWidgets, QtOpenGL
except ImportError:
    sys.exit(f'PySide6 is missing for {sys.executable}. Install PySide6 6.6 or newer for this interpreter.')
if tuple(int(part) for part in PySide6.__version__.split('.')[:2]) < (6, 6):
    sys.exit('Vela requires PySide6 6.6 or newer.')
for path in (destination, bin_dir, desktop.parent):
    path.mkdir(parents=True, exist_ok=True)
def copy_atomic(source, target):
    # Never truncate a library still mapped by an existing preview process.
    fd, temporary = tempfile.mkstemp(prefix='.vela-install-', dir=Path(target).parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(target)


shutil.copytree(root / 'vela', destination / 'vela', dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__'), copy_function=copy_atomic)
# Refresh an already enabled Vela order after Proton/library updates.
sys.path.insert(0, str(root))
from vela import layer_order
order_config = layer_order.settings_path()
try:
    if order_config.exists() and layer_order.owns_configuration(json.loads(order_config.read_text())):
        layer_order.configure()
except (OSError, ValueError, KeyError) as error:
    print(f'Could not refresh the optional LSFG fix: {error}', file=sys.stderr)
launcher = ('#!/bin/sh\n' +
            f'export PYTHONPATH={shlex.quote(str(destination))}${{PYTHONPATH:+:$PYTHONPATH}}\n' +
            f'exec {shlex.quote(sys.executable)} -m vela.ui "$@"\n')
path = bin_dir / 'vela'
path.write_text(launcher)
path.chmod(0o755)
# Opt-in game launcher; the system MangoHud installation stays untouched.
from vela.runtime import available as textured_runtime_available
if textured_runtime_available():
    game_launcher = bin_dir / 'vela-mangohud'
    game_launcher.write_text(launcher.replace('-m vela.ui', '-m vela.runtime'))
    game_launcher.chmod(0o755)
# Plasma caches icons by path; a content-based name invalidates old artwork.
icon_source = destination / 'vela/assets/vela.svg'
icon_digest = hashlib.sha256(icon_source.read_bytes()).hexdigest()[:12]
icon_path = icon_source.with_name(f'vela-{icon_digest}.svg')
shutil.copyfile(icon_source, icon_path)
exec_path = str(bin_dir / 'vela').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
desktop.write_text('[Desktop Entry]\nType=Application\nName=Vela\n'
                   'Comment=MangoHud customization and frame limiter\n'
                   f'Exec="{exec_path}"\nIcon={icon_path}\nTerminal=false\nCategories=Game;Utility;\n')
print(f'Installed Vela: {bin_dir / "vela"}')
