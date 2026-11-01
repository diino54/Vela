#!/usr/bin/env python3
"""Build the pinned rounded ReShade using clang-cl + SDK in a Podman container.

See native/reshade/README.md for toolchain setup. Never installs into a game.
SDK/MSVC files stay in --work; only final DLLs and hashes enter vela/native.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "18deaa52de0c425a78b329e9cb3c497281cd00ec"
IMGUI_REVISION = "3912b3d9a9c1b3f17431aebafd86d2f40ee6e59c"
VERSION = "6.8.0"


def run(args, **kwargs):
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def apply_patch(source, patch):
    reverse = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(patch)],
        cwd=source,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if reverse.returncode:
        run(["git", "apply", "--check", patch], cwd=source)
        run(["git", "apply", patch], cwd=source)


def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".vela-reshade-", dir=target.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, name)
        os.chmod(name, 0o644)
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/vela-reshade-work"))
    parser.add_argument("--container", default="vela-reshade-build")
    parser.add_argument("--arch", choices=("x64", "x86", "all"), default="all")
    parser.add_argument(
        "--skip-shaders",
        action="store_true",
        help="Reuse previously compiled shaders (only after no shader-source changes)",
    )
    args = parser.parse_args()
    work = args.work.resolve()
    source = work / "source"
    work.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        run(
            ["git", "clone", "--branch", "v6.8.0", "https://github.com/crosire/reshade.git", source]
        )
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual != REVISION:
        raise SystemExit("Unexpected ReShade source revision: " + actual)
    run(["git", "submodule", "update", "--init", "--depth", "1", "--jobs", "4"], cwd=source)
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source / "deps/imgui", text=True
    ).strip()
    if actual != IMGUI_REVISION:
        raise SystemExit("Unexpected ImGui revision: " + actual)
    visual_patch = ROOT / "native/reshade/visual-effects.patch"
    already_visual = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(visual_patch)],
        cwd=source,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if already_visual.returncode == 0:
        run(["git", "apply", "--reverse", visual_patch], cwd=source)
    for patch in ("rounded-ui.patch", "clang-build.patch", "visual-effects.patch"):
        apply_patch(source, ROOT / "native/reshade" / patch)
    for header in ("vela_rounding.hpp", "vela_font_scale.hpp", "vela_visual.hpp"):
        shutil.copyfile(ROOT / "native/reshade" / header, source / "source" / header)
    shader_sources = ROOT / "native/reshade/shaders"
    blur_functions = (shader_sources / "vela_blur.hlsl").read_text()
    for template in shader_sources.iterdir():
        if template.name == "vela_blur.hlsl":
            continue
        functions = blur_functions
        if template.suffix == ".glsl":
            functions = (
                functions.replace("float4", "vec4")
                .replace("float3", "vec3")
                .replace("float2", "vec2")
            )
        code = template.read_text().replace("// @VELA_BLUR_FUNCTIONS@", functions)
        (source / "res/shaders" / template.name).write_text(code)
    (source / "res/version.h").write_text(
        '#pragma once\n#define VERSION_FULL 6.8.0.4\n#define VERSION_MAJOR 6\n#define VERSION_MINOR 8\n#define VERSION_REVISION 0\n#define VERSION_BUILD 4\n#define VERSION_STRING_FILE "6.8.0.4"\n#define VERSION_STRING_PRODUCT "6.8.0 VELA UNOFFICIAL"\n'
    )
    run(["python3", ROOT / "scripts/reshade_sdk_case.py", work])
    if not args.skip_shaders:
        sdk_bins = [
            path
            for path in (work / "msvc/kits/10/bin").glob("10.*/x64")
            if (path / "fxc.exe").is_file()
        ]
        if not sdk_bins:
            raise SystemExit("Windows SDK FXC is missing")
        sdk_bin = max(sdk_bins, key=lambda path: tuple(map(int, path.parent.name.split("."))))
        prefix = work / "wine-shader-compiler"
        prefix.mkdir(exist_ok=True)
        env = dict(
            os.environ,
            WINEPREFIX=str(prefix),
            WINEDEBUG="-all",
            WINEDLLOVERRIDES="d3dcompiler_47=n",
        )
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        shaders = source / "res/shaders"
        for name, profile in [
            ("copy_ps", "ps_4_0"),
            ("fullscreen_vs", "vs_4_0"),
            ("imgui_ps_3_0", "ps_3_0"),
            ("imgui_ps_4_0", "ps_4_0"),
            ("imgui_vs_3_0", "vs_3_0"),
            ("imgui_vs_4_0", "vs_4_0"),
            ("mipmap_cs_5_0", "cs_5_0"),
        ]:
            run(
                [
                    "wine",
                    sdk_bin / "fxc.exe",
                    "/nologo",
                    "/T",
                    profile,
                    "/E",
                    "main",
                    "/O3",
                    "/Fo",
                    name + ".cso",
                    name + ".hlsl",
                ],
                cwd=shaders,
                env=env,
            )
        run(
            [
                "podman",
                "exec",
                args.container,
                "glslangValidator",
                "-V",
                "-S",
                "frag",
                "-I/work/source/res/shaders",
                "-Dfloat3=vec3",
                "-Dfloat1=float",
                "-Dfloat3x3=mat3",
                "/work/source/res/shaders/imgui_ps_450.glsl",
                "-o",
                "/work/source/res/shaders/imgui_ps_450.spv",
            ]
        )
    destination = ROOT / "vela/native/reshade"
    destination.mkdir(parents=True, exist_ok=True)
    metadata = {
        "version": VERSION,
        "variant": "Vela visual effects v4 (GPU backdrop and UI animation)",
        "upstream_revision": REVISION,
        "imgui_revision": IMGUI_REVISION,
        "sha256": {},
    }
    for arch in ("x64", "x86") if args.arch == "all" else (args.arch,):
        bits = 64 if arch == "x64" else 32
        build = "build" if bits == 64 else "build-x86"
        triple = "x86_64" if bits == 64 else "i686"
        toolchain = work / f"vela-toolchain-{arch}.cmake"
        toolchain.write_text(
            f"set(CMAKE_SYSTEM_NAME Windows)\nset(CMAKE_SYSTEM_PROCESSOR {'AMD64' if bits == 64 else 'x86'})\nset(CMAKE_C_COMPILER clang-cl)\nset(CMAKE_CXX_COMPILER clang-cl)\nset(CMAKE_C_COMPILER_TARGET {triple}-pc-windows-msvc)\nset(CMAKE_CXX_COMPILER_TARGET {triple}-pc-windows-msvc)\nset(CMAKE_LINKER lld-link)\nset(CMAKE_RC_COMPILER llvm-rc)\nset(CMAKE_MT llvm-mt)\nset(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)\n"
        )
        script = work / f"vela-build-{arch}.sh"
        script.write_text(
            "set -eu\nBIN=/work/msvc/bin/x64\n. /work/msvc-wine/msvcenv-native.sh\n"
            + ('export LIB="${LIB//x64/x86}"\n' if bits == 32 else "")
            + f"cmake -S /work/source -B /work/{build} -G Ninja -DCMAKE_TOOLCHAIN_FILE=/work/{toolchain.name} -DCMAKE_BUILD_TYPE=Release\ncmake --build /work/{build} -j 6\n"
        )
        run(["podman", "exec", args.container, "bash", "/work/" + script.name])
        binary = source.parent / build / f"ReShade{bits}.dll"
        # Same PE validation as the installer, without executing the DLL.
        import sys

        sys.path.insert(0, str(ROOT))
        from vela.reshade import pe_bits

        if pe_bits(binary) != bits:
            raise SystemExit("Wrong output architecture")
        atomic_copy(binary, destination / binary.name)
        metadata["sha256"][str(bits)] = hashlib.sha256(binary.read_bytes()).hexdigest()
    existing = destination / "BUILD.json"
    if existing.exists():
        old = json.loads(existing.read_text())
        if old.get("upstream_revision") == REVISION and old.get("variant") == metadata["variant"]:
            for bits, checksum in old.get("sha256", {}).items():
                binary = destination / f"ReShade{bits}.dll"
                if (
                    bits not in metadata["sha256"]
                    and binary.exists()
                    and hashlib.sha256(binary.read_bytes()).hexdigest() == checksum
                ):
                    metadata["sha256"][bits] = checksum
    existing.write_text(json.dumps(metadata, indent=2) + "\n")
    print("Built Vela ReShade:", ", ".join(metadata["sha256"]) + " bit")


if __name__ == "__main__":
    main()
