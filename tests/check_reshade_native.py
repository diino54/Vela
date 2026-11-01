"""Own-window Wine smoke for bundled ReShade. Requires the documented build SDK.

Compile only this repository's harness, launch in a dedicated temporary game
folder, and verify XRes PID before capturing its own XComposite surface.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture, client_pid

from vela.preview import XWindows
from vela.reshade import rounded_runtime
from vela.reshade_theme import vela_theme

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--work", type=Path, default=Path("/tmp/vela-reshade-work"))
parser.add_argument("--api", choices=("opengl", "d3d11"), default="opengl")
parser.add_argument(
    "--font-reset-check",
    action="store_true",
    help="Exercise explicit 13px/scale 1 through two actual swapchain resizes",
)
parser.add_argument("--bits", type=int, choices=(32, 64), default=64)
parser.add_argument(
    "--dxvk",
    type=Path,
    help="Optional existing DXVK directory containing dxgi.dll/d3d11.dll; copied only into the private test prefix",
)
parser.add_argument("--container", default="vela-reshade-build")
parser.add_argument("--output", type=Path, default=Path("/tmp/vela-reshade-native-check.png"))
args = parser.parse_args()
work = args.work.resolve()
folder = work / f"owned-smoke-{args.api}-{args.bits}"
folder.mkdir(exist_ok=True)
source = "smoke_win.cpp" if args.api == "opengl" else "smoke_d3d11_win.cpp"
shutil.copyfile(root / "native/reshade" / source, folder / source)
triple = "x86_64" if args.bits == 64 else "i686"
arch = "x64" if args.bits == 64 else "x86"
libraries = (
    "user32.lib gdi32.lib opengl32.lib" if args.api == "opengl" else "user32.lib d3d11.lib dxgi.lib"
)
script = folder / "compile.sh"
script.write_text(
    "set -eu\nBIN=/work/msvc/bin/x64\n. /work/msvc-wine/msvcenv-native.sh\n"
    + ('export LIB="${LIB//x64/x86}"\n' if args.bits == 32 else "")
    + f"cd /work/{folder.name}\nclang-cl -fuse-ld=lld --target={triple}-pc-windows-msvc /EHsc /O2 /MT /DUNICODE /D_UNICODE {source} /Fe:VelaOwnedTest.exe /link /subsystem:windows /entry:wWinMainCRTStartup {libraries}\n"
)
subprocess.run(
    ["podman", "exec", args.container, "bash", f"/work/{folder.name}/compile.sh"], check=True
)
hook = "opengl32" if args.api == "opengl" else "dxgi"
_, dll = rounded_runtime(args.bits)
(folder / (hook + ".dll")).write_bytes(dll)
config = "[GENERAL]\nPerformanceMode=1\n" + vela_theme().replace(
    "ShowFPS=0", "ShowFPS=0\nTutorialProgress=4"
)
if args.font_reset_check:
    assert args.api == "d3d11"
(folder / "ReShade.ini").write_text(config)
prefix = work / f"wine-own-test-{args.bits}"
prefix.mkdir(exist_ok=True)
token = uuid.uuid4().hex
env = dict(
    os.environ,
    VELA_OWNED_RESHADE_TEST=token,
    WINEPREFIX=str(prefix),
    WINEDLLOVERRIDES=f"{hook}=n,b",
    WINEDEBUG="-all",
)
# Only this harness uses this dedicated prefix; reset its server so child
# process environment contains this run's ownership token. Never use a global prefix.
subprocess.run(["wineserver", "-k"], env=env, check=False)
if args.dxvk:
    assert args.api == "d3d11" and args.bits == 64, (
        "This smoke currently supports DXVK with D3D11 x64"
    )
    init_env = dict(env)
    init_env.pop("DISPLAY", None)
    init_env.pop("WAYLAND_DISPLAY", None)
    subprocess.run(["wineboot", "-u"], env=init_env, check=True, timeout=60)
    for name in ("dxgi.dll", "d3d11.dll"):
        target = prefix / "drive_c/windows/system32" / name
        target.unlink(missing_ok=True)
        shutil.copyfile(args.dxvk / name, target)
    env["WINEDLLOVERRIDES"] = "dxgi,d3d11=n,b"
(folder / "owned-frame.ppm").unlink(missing_ok=True)
process = subprocess.Popen(
    ["wine", str(folder / "VelaOwnedTest.exe")]
    + (["--font-reset-check"] if args.font_reset_check else []),
    cwd=folder,
    env=env,
)
try:
    owner_pid = None
    if args.api == "d3d11":
        # Read only a staging texture exported by our own harness, including
        # when Wine/DXVK presents through Wayland instead of X11.
        from PIL import Image, ImageStat

        frame = folder / "owned-frame.ppm"
        for _ in range(400):
            if frame.exists() and frame.stat().st_size > 960 * 640 * 3:
                break
            time.sleep(0.1)
        if not frame.exists():
            raise RuntimeError("Own DirectX framebuffer was not exported")
        image = Image.open(frame)
        image.load()
        assert max(ImageStat.Stat(image).stddev) > 5, "No visible overlay in the owned framebuffer"
        image.save(args.output)
        print("Own DirectX framebuffer:", args.output)
    else:
        found = False
        owner_pid = None
        for _ in range(200):
            if process.poll() not in (None, 0):
                raise RuntimeError(f"Own test exited with {process.returncode}")
            connection = XWindows()
            try:
                for window, title in connection.windows().items():
                    if not title.startswith("Vela ReShade owned integration test"):
                        continue
                    candidate = client_pid(connection, window)
                    if _ % 20 == 0:
                        print("Own-title candidate:", repr(title), "PID", candidate, flush=True)
                    try:
                        environment = Path(f"/proc/{candidate}/environ").read_bytes().split(b"\0")
                    except OSError:
                        continue
                    if _ % 20 == 0:
                        print(
                            "Ownership token present:",
                            ("VELA_OWNED_RESHADE_TEST=" + token).encode() in environment,
                            flush=True,
                        )
                    if ("VELA_OWNED_RESHADE_TEST=" + token).encode() in environment:
                        owner_pid = candidate
                        found = True
                        break
            finally:
                connection.close()
            if found:
                break
            time.sleep(0.1)
        if not found:
            raise RuntimeError(
                "No window verified as owned by our launched process; refusing capture"
            )
        time.sleep(5)
        capture(owner_pid, str(args.output))
        print("Own native frame:", args.output)
finally:
    process.wait(timeout=40)
    if owner_pid and owner_pid != process.pid:
        for _ in range(400):
            try:
                state = Path(f"/proc/{owner_pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except OSError:
                break
            if state == "Z":
                break
            time.sleep(0.1)
log = (folder / "ReShade.log").read_text(errors="replace")
assert "6.8.0.3" in log and "Recreated runtime environment" in log
assert "Another ReShade instance" not in log
if args.font_reset_check:
    import re

    states = re.findall(r"Vela font state: base=([\d.]+) scale=([\d.]+).*?surface=(\d+x\d+)", log)
    assert len(states) >= 3, states
    assert all(float(base) == 13 and float(scale) == 1 for base, scale, _ in states), states
    assert any(surface.endswith("x1440") for _, _, surface in states), states
    print("PASS: font 13 / scale 1 preserved through actual GPU swapchain resets:", states)
print(
    f"PASS: bundled {args.bits}-bit ReShade, {args.api}, runtime initialized and own process exited cleanly"
)
