import os
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
msvc_version = next((root / "msvc/vc/tools/msvc").iterdir()).name
names = set()
for source in (
    root / "source",
    root / "msvc/kits/10/include",
    root / f"msvc/vc/tools/msvc/{msvc_version}/include",
):
    for base, _, files in os.walk(source):
        for name in files:
            if Path(name).suffix.lower() not in (".h", ".hpp", ".cpp", ".c", ".inl"):
                continue
            path = Path(base) / name
            if path.is_symlink():
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            names.update(
                m.group(1).replace("\\", "/").rsplit("/", 1)[-1]
                for m in re.finditer(r'#\s*include\s*[<"]([^">]+)', text)
            )
by_lower = {}
for name in names:
    by_lower.setdefault(name.casefold(), set()).add(name)
count = 0
for source in (root / "msvc/kits/10/include", root / f"msvc/vc/tools/msvc/{msvc_version}/include"):
    for base, _, files in os.walk(source):
        for name in files:
            for alias in by_lower.get(name.casefold(), ()):
                path = Path(base) / alias
                if not path.exists():
                    path.symlink_to(name)
                    count += 1
print("SDK header aliases:", count)
