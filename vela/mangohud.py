"""Control already-loaded MangoHud through its watched configuration file."""
from dataclasses import dataclass
import ctypes
import fcntl
import math
import os
from pathlib import Path
import re
import stat
import tempfile
from .settings import command_names, validate

BEGIN = '# BEGIN VELA'
END = '# END VELA'


def default_config():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'MangoHud/MangoHud.conf'


class ControlError(Exception):
    pass

@dataclass
class Session:
    pid: int
    start: str
    name: str
    config_dir: Path
    watched: Path | None
    explicit: bool
    reason: str = ''

    @property
    def identity(self):
        return self.pid, self.start

    @property
    def profile(self):
        name = self.name
        filename = f'wine-{name[:-4]}.conf' if name.lower().endswith('.exe') else f'{name}.conf'
        if any(c in filename for c in '/\\\0\r\n'):
            raise ControlError('Invalid process name.')
        return self.config_dir / filename


def read_environment(proc):
    return dict(item.split('=', 1) for item in
                (proc / 'environ').read_bytes().decode(errors='replace').split('\0') if '=' in item)


def start_time(proc):
    return (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]


def env_options(value):
    return {part.split('=', 1)[0].strip(): part.split('=', 1)[1].strip() if '=' in part else '1'
            for part in re.split(r'(?<!\\)[,;:]', value) if part.strip()}


def watch_details(proc):
    result = {}
    for fd in (proc / 'fdinfo').iterdir():
        try:
            for line in fd.read_text().splitlines():
                if not line.startswith('inotify wd:'):
                    continue
                fields = dict(item.split(':', 1) for item in line.split() if ':' in item)
                identity = int(fields['ino'], 16), int(fields['sdev'], 16)
                handle = None
                if fields.get('f_handle'):
                    handle = int(fields['fhandle-type'], 16), bytes.fromhex(fields['f_handle'])
                result[identity] = handle
        except (OSError, ValueError, KeyError):
            continue
    return result


def file_handle(path):
    # Btrfs stat() exposes a subvolume device number, but inotify reports the
    # superblock device. Compare export handles rather than guessing by inode.
    class Handle(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint), ('kind', ctypes.c_int), ('data', ctypes.c_ubyte * 128)]
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, 'name_to_handle_at', None)
    if function is None:
        return None
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.POINTER(Handle), ctypes.POINTER(ctypes.c_int), ctypes.c_int]
    function.restype = ctypes.c_int
    handle = Handle()
    handle.size = 128
    mount_id = ctypes.c_int()
    if function(-100, os.fsencode(path), ctypes.byref(handle), ctypes.byref(mount_id), 0) != 0:
        return None
    if handle.size > 128:
        return None
    return handle.kind, bytes(handle.data[:handle.size])


def file_id(path):
    info = path.stat()
    major, minor = os.major(info.st_dev), os.minor(info.st_dev)
    return info.st_ino, (minor & 0xff) | (major << 8) | ((minor & ~0xff) << 12)


def watched_config(proc, candidates):
    watches = watch_details(proc)
    for path in candidates:
        try:
            identity = file_id(path)
            if identity in watches:
                return path.resolve()
            same_inode = [handle for (inode, _), handle in watches.items() if inode == identity[0] and handle]
            if same_inode and file_handle(path) in same_inode:
                return path.resolve()
        except OSError:
            pass
    return None


def inspect(pid):
    proc = Path('/proc') / str(pid)
    if proc.stat().st_uid != os.getuid():
        return None
    maps = (proc / 'maps').read_text()
    if not re.search(r'/libMangoHud(?:_opengl)?\.so', maps):
        return None
    env = read_environment(proc)
    args = (proc / 'cmdline').read_bytes().rstrip(b'\0').decode(errors='replace').split('\0')
    names = command_names(args)
    exe = (proc / 'exe').readlink()
    name = next((name for name in names if name.lower().endswith('.exe')), exe.name)
    config_root = Path(env.get('XDG_CONFIG_HOME') or str(Path(env.get('HOME', str(Path.home()))) / '.config')) / 'MangoHud'
    candidates = []
    explicit = bool(env.get('MANGOHUD_CONFIGFILE'))
    if explicit:
        path = Path(env['MANGOHUD_CONFIGFILE'])
        if not path.is_absolute():
            path = (proc / 'cwd').resolve() / path
        candidates.append(path)
    else:
        candidates.extend(sorted(config_root.glob('*.conf')))
        candidates.extend([exe.parent / 'MangoHud.conf', (proc / 'cwd') / 'MangoHud.conf', Path('/etc/MangoHud.conf')])
    watched = watched_config(proc, candidates)
    options = env_options(env.get('MANGOHUD_CONFIG', ''))
    reason = ''
    if 'MANGOHUD_CONFIG' in env and options.get('read_cfg', '0') == '0':
        reason = 'MANGOHUD_CONFIG disables configuration files (missing read_cfg).'
    elif set(options) & {'fps_limit', 'fps_limit_method', 'no_display', 'preset'}:
        reason = 'MANGOHUD_CONFIG overrides limiter or overlay settings.'
    elif watched is None:
        reason = 'MangoHud is not watching an accessible configuration file.'
    return Session(int(pid), start_time(proc), name, config_root, watched, explicit, reason)


def discover():
    result = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            session = inspect(int(proc.name))
            if session:
                result.append(session)
        except (OSError, ValueError, IndexError):
            continue
    return sorted(result, key=lambda session: (session.name.lower(), session.pid))


def appearance_values(content):
    defaults = {'round_corners': 0., 'background_alpha': .5, 'font_size': 24., 'alpha': 1.,
                'font_scale': 1., 'font_size_text': 24., 'text_outline_thickness': 1.5, 'vela_padding': 5.,
                'vela_background_noise': 0., 'vela_background_blur': 0., 'vela_border_width': 0., 'vela_border_alpha': 1.,
                'vela_shadow_alpha': 0., 'vela_shadow_blur': 16.,
                'vela_shadow_offset_x': 0., 'vela_shadow_offset_y': 4.}
    for key in defaults:
        values = re.findall(r'^\s*' + key + r'\s*=\s*([^#\n]+)', content, re.M)
        if values:
            try:
                value = float(values[-1])
                low, high = {'round_corners': (0, 100), 'background_alpha': (0, 1),
                             'font_size': (1, 256), 'alpha': (0, 1), 'font_scale': (.1, 10),
                             'font_size_text': (1, 256), 'text_outline_thickness': (0, 10),
                             'vela_background_noise': (0, 1), 'vela_background_blur': (0, 32), 'vela_border_width': (0, 8),
                             'vela_border_alpha': (0, 1), 'vela_shadow_alpha': (0, 1),
                             'vela_shadow_blur': (0, 40), 'vela_shadow_offset_x': (-40, 40),
                             'vela_shadow_offset_y': (-40, 40), 'vela_padding': (0, 64)}[key]
                if low <= value <= high:
                    defaults[key] = value
            except ValueError:
                pass
    return defaults


def color_values(content):
    values = {'text_color': 'FFFFFF', 'background_color': '020202', 'text_outline_color': '000000',
              'vela_border_color': '414141', 'vela_shadow_color': '000000'}
    for raw in content.splitlines():
        key, _, value = raw.split('#', 1)[0].strip().partition('=')
        if key.strip() in values and re.fullmatch(r'[0-9a-fA-F]{6}', value.strip()):
            values[key.strip()] = value.strip().upper()
    return values


def text_values(content):
    values = {'text_outline': True, 'no_small_font': False}
    for raw in content.splitlines():
        key, _, value = raw.split('#', 1)[0].strip().partition('=')
        if key.strip() in values:
            values[key.strip()] = value.strip().lower() not in ('0', 'false')
    return values


METRIC_KEYS = ('fps', 'frametime', 'frame_timing', 'gpu_stats', 'gpu_temp', 'cpu_stats', 'cpu_temp', 'ram', 'vram',
               'gamemode', 'vkbasalt', 'engine_version', 'vulkan_driver', 'wine')


def metric_values(content):
    values = {key: key in ('fps', 'frametime', 'frame_timing', 'gpu_stats', 'cpu_stats')
              for key in METRIC_KEYS}
    for raw in content.splitlines():
        line = raw.split('#', 1)[0].strip()
        key, _, value = line.partition('=')
        if key.strip() in values:
            values[key.strip()] = value.strip().lower() not in ('0', 'false')
    return values


def font_values(content):
    values = {'font_file': '', 'font_file_text': ''}
    for raw in content.splitlines():
        key, separator, value = raw.split('#', 1)[0].strip().partition('=')
        if separator and key.strip() in values:
            values[key.strip()] = value.strip()
    return values


def managed_content(content, fps, method, show_hud, appearance=None):
    if method not in ('early', 'late'):
        raise ControlError('Unknown limiter mode.')
    validate('process', fps)
    # Remove the retired effect when saving or preparing a preview.
    content = ''.join(line for line in content.splitlines(keepends=True)
                      if line.split('#', 1)[0].partition('=')[0].strip() != 'vela_background_frost')
    saved_appearance = {}
    for key, value in font_values(content).items():
        if re.search(r'^\s*' + key + r'\s*=', content, re.M):
            saved_appearance[key] = value
    for key, value in text_values(content).items():
        if re.search(r'^\s*' + key + r'\s*(?:=|$)', content, re.M):
            saved_appearance[key] = int(value)
    for key, value in color_values(content).items():
        if re.search(r'^\s*' + key + r'\s*=', content, re.M):
            saved_appearance[key] = value
    for key, value in appearance_values(content).items():
        if re.search(r'^\s*' + key + r'\s*=', content, re.M):
            saved_appearance[key] = value
    for key, value in metric_values(content).items():
        if re.search(r'^\s*' + key + r'\s*(?:=|$)', content, re.M):
            saved_appearance[key] = int(value)
    if appearance is not None:
        saved_appearance.update(appearance)
    saved_appearance.pop('vela_background_frost', None)
    # Canonical order for the extension regardless of which options were read
    # from disk first. Do not reorder metrics: their order controls HUD layout.
    for key in ('vela_padding', 'vela_background_noise', 'vela_background_blur', 'vela_border_color', 'vela_border_width', 'vela_border_alpha',
                'vela_shadow_color', 'vela_shadow_alpha', 'vela_shadow_blur',
                'vela_shadow_offset_x', 'vela_shadow_offset_y'):
        if key in saved_appearance:
            saved_appearance[key] = saved_appearance.pop(key)
    extra = ''
    for key, value in saved_appearance.items():
        if key == 'vela_padding':
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 64:
                raise ControlError('Padding must be between 0 and 64 px.')
            if value == 5 and not re.search(r'^\s*vela_padding\s*=', content, re.M):
                continue
        if key == 'vela_background_blur':
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 32:
                raise ControlError('Background blur must be between 0 and 32 px.')
            if not value and not re.search(r'^\s*vela_background_blur\s*=', content, re.M):
                continue
        if key == 'vela_background_noise':
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ControlError('Background effects must be between 0 and 1.')
            # Keep default configurations compatible with stock MangoHud.
            # An explicit zero is needed if an earlier setting must be overridden.
            if not value and not re.search(r'^\s*' + key + r'\s*=', content, re.M):
                continue
        if key in ('vela_border_width', 'vela_border_alpha'):
            high = 8 if key == 'vela_border_width' else 1
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= high:
                raise ControlError('Border width must be 0–8 px and opacity must be 0–100%.')
        if key in ('vela_border_color', 'vela_border_width', 'vela_border_alpha'):
            default = {'vela_border_color': '414141', 'vela_border_width': 0, 'vela_border_alpha': 1}[key]
            if value == default and not re.search(r'^\s*' + key + r'\s*=', content, re.M):
                continue
        if key.startswith('vela_shadow_'):
            defaults = {'vela_shadow_color': '000000', 'vela_shadow_alpha': 0,
                        'vela_shadow_blur': 16, 'vela_shadow_offset_x': 0, 'vela_shadow_offset_y': 4}
            if key not in defaults:
                raise ControlError('Unknown shadow setting.')
            if key != 'vela_shadow_color':
                low, high = {'vela_shadow_alpha': (0, 1), 'vela_shadow_blur': (0, 40),
                             'vela_shadow_offset_x': (-40, 40), 'vela_shadow_offset_y': (-40, 40)}[key]
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                    raise ControlError('Invalid shadow opacity, softness or offset.')
            if value == defaults[key] and not re.search(r'^\s*' + key + r'\s*=', content, re.M):
                continue
        if key in ('font_file', 'font_file_text'):
            if not isinstance(value, str) or any(c in value for c in '\r\n\0#'):
                raise ControlError('Font paths cannot contain line breaks, null characters or #.')
            extra += f'{key}={value}\n'
        elif key in ('text_color', 'background_color', 'text_outline_color', 'vela_border_color', 'vela_shadow_color'):
            if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F]{6}', value):
                raise ControlError('Colors must use six hexadecimal digits (RRGGBB).')
            extra += f'{key}={value.upper()}\n'
        else:
            extra += f'{key}={value:g}\n'
    content = re.sub(r'(?m)^# BEGIN VELA\n.*?^# END VELA\n?', '', content, flags=re.S)
    return (content.rstrip('\n') + '\n\n' if content else '') + (
        f'{BEGIN}\nfps_limit={fps:g}\nfps_limit_method={method}\n'
        f'no_display={0 if show_hud else 1}\n{extra}{END}\n')


def edit_watched(path, transform, skip_unchanged=False):
    # Preserve inode: MangoHud watches the file rather than the directory.
    with path.open('r+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        info = os.fstat(stream.fileno())
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
            raise ControlError('The configuration must be a regular file owned by the current user.')
        previous = stream.read()
        content = transform(previous)
        if skip_unchanged and content == previous:
            return
        stream.seek(0)
        stream.write(content)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())


def replace_watched(path, content):
    edit_watched(path, lambda previous: content)


def values_from_content(content):
    options = {}
    for line in content.splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            key, separator, value = line.partition('=')
            options[key.strip()] = value.strip() if separator else '1'
    try:
        fps = float(options.get('fps_limit', '0').split(',')[0])
    except ValueError:
        fps = 0
    if not math.isfinite(fps) or not 0 <= fps <= 1000:
        fps = 0
    method = options.get('fps_limit_method', 'early')
    return fps, method if method in ('early', 'late') else 'early', options.get('no_display', '0').lower() not in ('1', 'true')


def config_values(path):
    try:
        content = path.read_text() if path else ''
    except FileNotFoundError:
        content = ''
    return values_from_content(content)


def save_appearance(path, appearance, template=None):
    """Save editor values, preserving the file's limiter and unrelated options.

    Existing watched files keep their inode. The read/modify/write operation is
    held under one lock so cooperating Vela instances do not lose updates.
    """
    def updated(content):
        return managed_content(content, *values_from_content(content), appearance).encode()

    if path.exists():
        edit_watched(path, lambda previous: updated(previous.decode('utf-8')), skip_unchanged=True)
    else:
        content = template.read_text() if template and template.exists() else ''
        content = updated(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation avoids overwriting a profile created concurrently.
        with path.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())


def profile_config(session, global_config=None):
    """Choose existing game settings before falling back to the global template."""
    if session.explicit and session.watched:
        return session.watched
    if session.profile.is_file():
        return session.profile
    global_path = Path(global_config).expanduser() if global_config else session.config_dir / 'MangoHud.conf'
    return global_path if global_path.is_file() else session.watched


def apply(session, fps, method='early', show_hud=False, appearance=None, global_config=None):
    current = inspect(session.pid)
    if current is None or current.identity != session.identity:
        raise ControlError('The selected application is no longer running.')
    if current.reason:
        raise ControlError(current.reason)
    source = current.watched
    if source is None:
        raise ControlError('MangoHud configuration not found.')
    if source.stat().st_uid != os.getuid():
        raise ControlError('MangoHud is watching a system file; it cannot be changed.')
    if current.explicit:
        others = [other for other in discover() if other.pid != current.pid and other.watched == source]
        if others:
            raise ControlError('This configuration file is shared with another MangoHud application.')
        target = source
    else:
        if current.profile.is_symlink():
            raise ControlError('The MangoHud profile is a symlink; the shared file will not be changed.')
        target = current.profile.resolve()
    def updated(previous):
        return managed_content(previous.decode('utf-8'), fps, method, show_hud, appearance).encode()

    if target == source:
        edit_watched(source, updated)
    else:
        # Create a per-game profile; nudge the current watcher to re-evaluate
        # config precedence and move its watch to that profile.
        target.parent.mkdir(parents=True, exist_ok=True)
        template = profile_config(current, global_config)
        base = template.read_text() if template else ''
        content = managed_content(base, fps, method, show_hud, appearance).encode()
        if target.exists():
            edit_watched(target, updated)
        else:
            fd, temp = tempfile.mkstemp(prefix='.vela-', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, target)
            finally:
                Path(temp).unlink(missing_ok=True)
        edit_watched(source, lambda previous: previous or b'\n')
    return target
