"""Order MangoHud before lsfg-vk using Vulkan Loader 1.4.304+ settings.

Auto controls preserve each layer's original enable/disable conditions.
Steam Runtime needs its own MangoHud manifest with /run/host library paths.
"""
import json
import os
from pathlib import Path
import tempfile

GENERATOR = 'vela-mangohud-before-lsfg-v1'



def owns_configuration(document):
    return isinstance(document, dict) and document.get('vela_generator') == GENERATOR


def configuration_status(home=None):
    """Return the saved fix's state; this does not inspect running games."""
    output = settings_path(home)
    try:
        document = json.loads(output.read_text())
    except FileNotFoundError:
        return 'missing', 'The LSFG layer-order fix is not configured.'
    except (OSError, ValueError, UnicodeError):
        return 'invalid', f'Cannot read the Vulkan Loader configuration: {output}'
    if not owns_configuration(document):
        return 'foreign', f'Another tool owns the Vulkan Loader configuration: {output}'
    try:
        entries = document['settings_array']
        if document['file_format_version'] != '1.0.0' or not entries:
            raise ValueError
        if not any('app_keys' not in entry for entry in entries):
            raise ValueError
        for entry in entries:
            layers = entry['layers']
            separator = layers.index({'control': 'unordered_layer_location'})
            before, after = layers[:separator], layers[separator + 1:]
            if not before or not after:
                raise ValueError
            for group, expected in ((before, 'MangoHud'), (after, 'LSFG')):
                for layer in group:
                    if (expected.lower() not in layer['name'].lower()
                            or layer['control'] != 'auto'
                            or layer.get('treat_as_implicit_manifest') is not True
                            or not Path(layer['path']).is_file()):
                        raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError, OSError):
        return 'invalid', 'The saved LSFG fix is incomplete or disabled. Apply it again to repair it.'
    return 'enabled', 'LSFG layer ordering is configured. Restart games started before enabling it. This does not enable frame generation itself.'


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.vela-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def ordered_layers(mango, lsfg):
    def entry(name, path):
        return dict(name=name, path=str(path), control='auto', treat_as_implicit_manifest=True)
    return ([entry(name, path) for name, path in mango] +
            [dict(control='unordered_layer_location')] +
            [entry(name, path) for name, path in lsfg])


def proton_executables(home):
    result = set()
    roots = [home / '.local/share/Steam', home / '.steam/root']
    for root in roots:
        patterns = ('compatibilitytools.d/*/files/**/wine*preloader',
                    'steamapps/common/Proton*/files/**/wine*preloader')
        for pattern in patterns:
            for path in root.glob(pattern):
                if path.is_file():
                    result.update((str(path), str(path.resolve())))
    return sorted(result)


def settings_path(home=None, data=None):
    home = Path(home or Path.home())
    # Loader checks HOME before XDG_DATA_HOME. Use its first lookup location.
    return home / '.local/share/vulkan/loader_settings.d/vk_loader_settings.json'


def configure(home=None, data=None):
    home = Path(home or Path.home())
    data = Path(data or os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    output = settings_path(home)
    if output.exists():
        existing = json.loads(output.read_text())
        if not owns_configuration(existing):
            raise ValueError(f'Another tool owns the loader configuration: {output}. It has not been overwritten.')
    directory = data / 'vela/layers'
    host_mango, runtime_mango, lsfg = [], [], []
    for suffix, arch in (('x86_64', '64'), ('x86', '32')):
        source = Path(f'/usr/share/vulkan/implicit_layer.d/MangoHud.{suffix}.json')
        if source.exists():
            manifest = json.loads(source.read_text())
            manifest['layer']['library_arch'] = arch
            # Keep original GIPA/GDPA mappings and enable/disable conditions.
            host = directory / f'MangoHud.host.{suffix}.json'
            write_json(host, manifest)
            host_mango.append((manifest['layer']['name'], host))
            runtime = directory / f'MangoHud.runtime.{suffix}.json'
            manifest['layer']['library_path'] = '/run/host' + manifest['layer']['library_path']
            write_json(runtime, manifest)
            runtime_mango.append((manifest['layer']['name'], runtime))
    for suffix, arch in (('', '64'), ('.x86', '32')):
        source = home / f'.local/share/vulkan/implicit_layer.d/VkLayer_LSFGVK_frame_generation{suffix}.json'
        if source.exists():
            manifest = json.loads(source.read_text())
            library = Path(manifest['layer']['library_path'])
            if not library.is_absolute():
                library = (source.parent / library).resolve()
            manifest['layer']['library_path'] = str(library)
            manifest['layer']['library_arch'] = arch
            target = directory / f'lsfg{suffix}.json'
            write_json(target, manifest)
            lsfg.append((manifest['layer']['name'], target))
    if not host_mango or not lsfg:
        raise ValueError('MangoHud and lsfg-vk manifests were not found.')
    entries = []
    keys = proton_executables(home)
    if keys:
        entries.append(dict(app_keys=keys, layers=ordered_layers(runtime_mango, lsfg)))
    entries.append(dict(layers=ordered_layers(host_mango, lsfg)))
    document = dict(file_format_version='1.0.0', settings_array=entries, vela_generator=GENERATOR)
    write_json(output, document)
    return output


def remove(home=None, data=None):
    home = Path(home or Path.home())
    data = Path(data or os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    directory = data / 'vela/layers'
    if directory.is_symlink():
        raise ValueError('Cannot remove layer manifests through a symlink directory.')
    output = settings_path(home)
    if output.exists():
        document = json.loads(output.read_text())
        if not owns_configuration(document):
            raise ValueError('Cannot remove a loader configuration owned by another tool.')
        output.unlink()
    for name in ('MangoHud.host.x86_64.json', 'MangoHud.runtime.x86_64.json',
                 'MangoHud.host.x86.json', 'MangoHud.runtime.x86.json',
                 'lsfg.json', 'lsfg.x86.json'):
        (directory / name).unlink(missing_ok=True)
    if directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
