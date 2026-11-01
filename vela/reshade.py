"""ReShade for Windows games under Proton/Wine.

No setup executable is run. Download upstream's standard setup, extract its
embedded DLL, stage everything locally, then exclusively publish new files.
An ownership journal permits removal without deleting user-modified files.
"""

import hashlib
import json
import os
import re
import stat
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen

from .reshade_theme import vela_theme
from .steam_library import app_types, is_game

HOME = "https://reshade.me/"
APIS = {"DirectX 10 / 11 / 12": "dxgi", "DirectX 9": "d3d9", "OpenGL (Windows)": "opengl32"}
PACKAGES = {
    "standard": (
        "Standard utilities",
        "ReShade headers, depth display and reference utilities.",
        "https://codeload.github.com/crosire/reshade-shaders/zip/refs/heads/slim",
    ),
    "sweetfx": (
        "SweetFX · CeeJay.dk",
        "Color correction, sharpening, SMAA and classic post-processing effects.",
        "https://codeload.github.com/CeeJayDK/SweetFX/zip/refs/heads/master",
    ),
    "quint": (
        "qUINT · Marty McFly",
        "MXAO, depth of field, Lightroom, bloom and more.",
        "https://codeload.github.com/martymcmodding/qUINT/zip/refs/heads/master",
    ),
}
JOURNAL = ".vela-reshade.json"
SHADERS = "vela-reshade-shaders"
HOOKS = ("dxgi.dll", "d3d9.dll", "d3d10.dll", "d3d11.dll", "d3d12.dll", "opengl32.dll")


@dataclass(frozen=True)
class Plan:
    executable: Path
    hook: str
    packages: tuple = ("standard",)
    preset: Path | None = None
    vela_ui: bool = True
    rounded_ui: bool = False


def pe_bits(path):
    """Read only the DOS/COFF headers; do not execute a foreign binary."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Select a regular Windows executable file.")
        if stream.read(2) != b"MZ":
            raise ValueError("Select a Windows game executable (.exe).")
        stream.seek(0x3C)
        offset = stream.read(4)
        if len(offset) != 4:
            raise ValueError("Truncated Windows executable.")
        stream.seek(struct.unpack("<I", offset)[0])
        header = stream.read(6)
    if header[:4] != b"PE\0\0" or len(header) != 6:
        raise ValueError("Invalid Windows executable header.")
    machine = struct.unpack("<H", header[4:])[0]
    if machine not in (0x14C, 0x8664):
        raise ValueError("Only x86 and x64 Windows games are supported.")
    return 64 if machine == 0x8664 else 32


class ExistingInstallationError(ValueError):
    """A valid game target contains protected files; not an invalid EXE."""


def validate(plan):
    exe = plan.executable.expanduser().resolve(strict=True)
    if not exe.is_file() or exe.suffix.lower() != ".exe":
        raise ValueError(
            "Select the actual game .exe, usually in Binaries/Win64, not its launcher."
        )
    bits = pe_bits(exe)
    if plan.hook not in APIS.values() or any(key not in PACKAGES for key in plan.packages):
        raise ValueError("Unsupported API or shader package.")
    folder = exe.parent
    # Case-insensitive checks matter on Wine even on a case-sensitive filesystem.
    names = {p.name.casefold() for p in folder.iterdir()}
    conflicts = names.intersection({*HOOKS, "reshade.ini", "velapreset.ini", JOURNAL, SHADERS})
    if conflicts:
        raise ExistingInstallationError(
            "Existing files found: "
            + ", ".join(sorted(conflicts))
            + ". Remove the previous installation first; Vela will not overwrite it."
        )
    if plan.preset:
        if plan.preset.suffix.lower() != ".ini" or not plan.preset.is_file():
            raise ValueError("Choose a ReShade preset .ini file.")
        if plan.preset.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Preset is too large.")
    return exe, bits


def fetch(url, report=lambda message: None):
    """Bounded HTTPS-only downloads; no shell, global Wine or Steam mutations."""
    if not url.startswith("https://"):
        raise ValueError("An HTTPS download is required.")
    request = Request(url, headers={"User-Agent": "Vela-ReShade/1.0"})
    with urlopen(request, timeout=25) as response:
        if not response.url.startswith("https://"):
            raise ValueError("An insecure download redirect was rejected.")
        chunks = []
        size = 0
        while chunk := response.read(256 * 1024):
            size += len(chunk)
            if size > 128 * 1024 * 1024:
                raise ValueError("Download exceeds the 128 MiB limit.")
            chunks.append(chunk)
            report(f"Downloaded {size / 1048576:.1f} MiB")
    return b"".join(chunks)


def latest_setup(page):
    versions = re.findall(
        r"(?:https://reshade\.me)?/?downloads/ReShade_Setup_(\d+\.\d+\.\d+)\.exe",
        page.decode("utf-8", errors="replace"),
    )
    if not versions:
        raise ValueError("Cannot find the standard installer on reshade.me. Try again later.")
    version = max(versions, key=lambda value: tuple(map(int, value.split("."))))
    return version, f"https://reshade.me/downloads/ReShade_Setup_{version}.exe"


def runtime_dll(setup, bits):
    # Python's ZipFile supports the self-extracting ZIP attached to official setup.
    with zipfile.ZipFile(BytesIO(setup)) as archive:
        info = archive.getinfo(f"ReShade{bits}.dll")
        if info.file_size > 64 * 1024 * 1024:
            raise ValueError("ReShade runtime is unexpectedly large.")
        dll = archive.read(info)
    # Validate architecture independently of the downloaded archive's filename.
    if len(dll) < 64 or dll[:2] != b"MZ":
        raise ValueError("Invalid ReShade runtime.")
    offset = struct.unpack_from("<I", dll, 0x3C)[0]
    expected = 0x8664 if bits == 64 else 0x14C
    if (
        offset + 6 > len(dll)
        or dll[offset : offset + 4] != b"PE\0\0"
        or struct.unpack_from("<H", dll, offset + 4)[0] != expected
    ):
        raise ValueError("Downloaded runtime has the wrong architecture.")
    return dll


def package_files(blob, key):
    result = {}
    total = 0
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                raise ValueError("Unsafe shader archive path.")
            if info.is_dir() or len(path.parts) < 2:
                continue
            relative = PurePosixPath(*path.parts[1:])
            # Retain package licensing alongside the actual shaders/textures.
            if relative.parts[0] not in (
                "Shaders",
                "Textures",
            ) and not relative.name.lower().startswith(("license", "readme", "copying")):
                continue
            total += info.file_size
            if total > 256 * 1024 * 1024 or len(result) >= 4096:
                raise ValueError("Shader archive exceeds extraction limits.")
            result[f"{SHADERS}/{key}/{relative}"] = archive.read(info)
    if not any("/Shaders/" in name and name.endswith(".fx") for name in result):
        raise ValueError("The shader package contains no effects.")
    return result


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rounded_runtime(bits):
    """Return the pinned Vela build only after checking architecture and hash."""
    directory = Path(__file__).parent / "native/reshade"
    metadata = json.loads((directory / "BUILD.json").read_text())
    path = directory / f"ReShade{bits}.dll"
    data = path.read_bytes()
    if pe_bits(path) != bits or digest(data) != metadata["sha256"][str(bits)]:
        raise ValueError("The Vela ReShade runtime is corrupted. Reinstall Vela.")
    return metadata["version"], data


def rounded_available(bits):
    directory = Path(__file__).parent / "native/reshade"
    try:
        metadata = json.loads((directory / "BUILD.json").read_text())
        return (
            str(bits) in metadata.get("sha256", {}) and (directory / f"ReShade{bits}.dll").is_file()
        )
    except (OSError, ValueError, TypeError):
        return False


def install(plan, report=lambda message: None, download=fetch):
    exe, bits = validate(plan)
    if plan.rounded_ui:
        report(f"Preparing Vela ReShade · rounded outer window · {bits}-bit…")
        version, dll = rounded_runtime(bits)
    else:
        report("Checking the latest standard ReShade release…")
        version, url = latest_setup(download(HOME))
        report(f"Downloading ReShade {version} · {bits}-bit…")
        dll = runtime_dll(download(url), bits)
    files = {plan.hook + ".dll": dll}
    if plan.rounded_ui:
        license_path = Path(__file__).parent / "native/reshade/LICENSES.txt"
        files[f"{SHADERS}/runtime/LICENSES.txt"] = license_path.read_bytes()
    for key in plan.packages:
        report("Downloading " + PACKAGES[key][0] + "…")
        files.update(package_files(download(PACKAGES[key][2]), key))
    effects = ",".join(f".\\{SHADERS}\\{key}\\Shaders\\**" for key in plan.packages)
    textures = ",".join(f".\\{SHADERS}\\{key}\\Textures\\**" for key in plan.packages)
    files["ReShade.ini"] = (
        f"[GENERAL]\nEffectSearchPaths={effects}\nTextureSearchPaths={textures}\nPresetPath=.\\VelaPreset.ini\n"
    ).encode()
    if plan.rounded_ui:
        files["ReShade.ini"] += (
            b"\n[VELA]\nBackgroundBlur=16\nBlurQuality=1\nAnimations=1\nAnimationDuration=0.24\n"
        )
    if plan.vela_ui:
        files["ReShade.ini"] += vela_theme().encode()
    elif plan.rounded_ui:
        files["ReShade.ini"] += b"\n[STYLE]\nWindowRounding=12\n"
    files["VelaPreset.ini"] = (
        plan.preset.read_bytes() if plan.preset else b"Techniques=\nTechniqueSorting=\n"
    )
    manifest = {
        "schema": 1,
        "version": version,
        "executable": exe.name,
        "hook": plan.hook,
        "runtime": "vela-rounded" if plan.rounded_ui else "official",
        "files": {name: digest(data) for name, data in files.items()},
    }
    files[JOURNAL] = (json.dumps(manifest, indent=2) + "\n").encode()
    report("Installing runtime and effects…")
    validate(plan)  # Recheck after downloads, before any game-directory writes.
    published = []
    directories = []
    with tempfile.TemporaryDirectory(prefix=".vela-reshade-", dir=exe.parent) as temporary:
        stage = Path(temporary)
        for index, (name, data) in enumerate(files.items()):
            (stage / str(index)).write_bytes(data)
        try:
            for index, name in enumerate(files):
                target = exe.parent / name
                for parent in reversed(target.parent.relative_to(exe.parent).parents):
                    candidate = exe.parent / parent
                    if candidate != exe.parent and candidate not in directories:
                        candidate.mkdir()
                        directories.append(candidate)
                if target.parent != exe.parent and target.parent not in directories:
                    target.parent.mkdir()
                    directories.append(target.parent)
                # Exclusive publication: refuse replacement, including symlinks.
                os.link(stage / str(index), target)
                published.append((target, files[name]))
        except Exception:
            for target, data in reversed(published):
                if not target.is_symlink() and target.read_bytes() == data:
                    target.unlink()
            for directory in reversed(directories):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise
    return manifest


def removal_inventory(executable):
    """Validate the entire ownership journal before planning any deletion."""
    folder = Path(executable).resolve(strict=True).parent
    journal = folder / JOURNAL
    if journal.is_symlink():
        raise ValueError("Refusing a symbolic ownership journal.")
    manifest = json.loads(journal.read_text())
    if (
        manifest.get("schema") != 1
        or manifest.get("hook") not in APIS.values()
        or not isinstance(manifest.get("files"), dict)
    ):
        raise ValueError("Invalid Vela installation journal.")
    targets = []
    for name, checksum in manifest["files"].items():
        relative = PurePosixPath(name)
        allowed = name in (manifest["hook"] + ".dll", "ReShade.ini", "VelaPreset.ini") or (
            relative.parts and relative.parts[0] == SHADERS
        )
        if not allowed or relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Invalid path in Vela installation journal.")
        target = folder / name
        if any(p.is_symlink() for p in (target, *target.parents) if p != folder):
            raise ValueError("Refusing symbolic links in the installation.")
        targets.append((target, checksum))
    return folder, journal, manifest, targets


def complete_removal_files(executable):
    """Include edited/new files inside Vela's dedicated shader tree and logs.

    Never follow symlinks or infer ownership of arbitrary root-level game files.
    """
    folder, journal, manifest, targets = removal_inventory(executable)
    files = {target for target, _ in targets if target.exists()}
    files.update(
        folder / name
        for name in (
            manifest["hook"] + ".dll",
            "ReShade.ini",
            "VelaPreset.ini",
            "ReShade.log",
            "ReShade.log.old",
        )
        if (folder / name).exists()
    )
    tree = folder / SHADERS
    if tree.is_symlink():
        raise ValueError("Refusing a symbolic shader directory.")
    if tree.exists():
        for root, directories, names in os.walk(tree, followlinks=False):
            for name in (*directories, *names):
                path = Path(root) / name
                if path.is_symlink():
                    raise ValueError("Refusing symbolic links in the shader directory.")
            files.update(Path(root) / name for name in names)
    for target in files:
        if target.is_symlink() or not target.is_file():
            raise ValueError("Refusing a non-regular ReShade file: " + target.name)
    files.add(journal)
    return sorted(str(target.relative_to(folder)) for target in files)


def uninstall(executable, complete=False):
    """Preserve modified files by default; complete mode is an explicit UI choice."""
    folder, journal, manifest, targets = removal_inventory(executable)
    if complete:
        names = complete_removal_files(executable)
        # The inventory is validated in full before deleting anything.
        for name in names:
            if name != JOURNAL:
                target = folder / name
                if target.is_symlink():
                    raise ValueError("Refusing a symbolic ReShade file.")
                target.unlink()
        tree = folder / SHADERS
        if tree.exists():
            for root, directories, _ in os.walk(tree, topdown=False):
                for name in directories:
                    (Path(root) / name).rmdir()
            tree.rmdir()
        journal.unlink()
        return []
    preserved = []
    directories = set()
    for target, checksum in targets:
        if not target.exists():
            continue
        if not target.is_file() or digest(target.read_bytes()) != checksum:
            preserved.append(str(target.relative_to(folder)))
            continue
        target.unlink()
        directories.update(p for p in target.parents if p != folder and folder in p.parents)
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    if preserved:
        # Keep ownership for remaining modified files and allow later retry.
        manifest["files"] = {name: manifest["files"][name] for name in preserved}
        journal.write_text(json.dumps(manifest, indent=2) + "\n")
    else:
        journal.unlink()
    return preserved


def launch_options(hook, existing="%command%"):
    if hook not in APIS.values():
        raise ValueError("Unsupported API.")
    existing = existing.strip() or "%command%"
    if existing.count("%command%") != 1 or "\n" in existing or "\r" in existing:
        raise ValueError("Launch options must contain exactly one %command%.")
    pattern = r"""(?<!\S)WINEDLLOVERRIDES=(?:"([^"]*)"|'([^']*)'|([^\s]+))"""
    match = re.search(pattern, existing)
    value = next((group for group in match.groups() if group is not None), "") if match else ""
    entries = [
        entry for entry in value.split(";") if entry and entry.split("=")[0].casefold() != hook
    ]
    entries.append(hook + "=n,b")
    override = 'WINEDLLOVERRIDES="' + ";".join(entries) + '"'
    return (
        existing[: match.start()] + override + existing[match.end() :]
        if match
        else override + " " + existing
    )


def steam_games():
    """Small local Steam library index; never recursively scan the home directory."""
    roots = {
        Path.home() / ".steam/steam",
        Path.home() / ".local/share/Steam",
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
    }
    caches = [root / "appcache/appinfo.vdf" for root in roots]
    candidates = []
    for root in tuple(roots):
        try:
            text = (root / "steamapps/libraryfolders.vdf").read_text()
            roots.update(
                Path(path.replace("\\\\", "\\")) for path in re.findall(r'"path"\s+"([^"]+)"', text)
            )
        except OSError:
            pass
    for root in roots:
        for manifest in (root / "steamapps").glob("appmanifest_*.acf"):
            try:
                text = manifest.read_text()
                name = re.search(r'"name"\s+"([^"]+)"', text)
                directory = re.search(r'"installdir"\s+"([^"]+)"', text)
                if name and directory:
                    relative = Path(directory[1])
                    if relative.is_absolute() or ".." in relative.parts:
                        continue
                    path = root / "steamapps/common" / relative
                    if path.is_dir():
                        appid = int(manifest.stem.removeprefix("appmanifest_"))
                        candidates.append((appid, name[1], path.resolve()))
            except (OSError, ValueError):
                pass
    kinds = app_types(caches, {appid for appid, _, _ in candidates})
    games = {str(path): name for appid, name, path in candidates if is_game(name, kinds.get(appid))}
    return sorted(
        ((name, Path(path)) for path, name in games.items()), key=lambda item: item[0].casefold()
    )
