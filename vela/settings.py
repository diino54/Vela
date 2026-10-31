"""Input validation and Linux/Wine process-name helpers."""
import math


def validate(process, fps):
    process = process.strip()
    if (not process or len(process.encode()) > 255 or
            any(c in process for c in "\t\r\n/\\\0") or process in (".", "..")):
        raise ValueError("Enter a process name only, for example Cyberpunk2077.exe.")
    if not math.isfinite(fps) or not 0 <= fps <= 1000:
        raise ValueError("The limit must be between 0 and 1000 FPS; 0 means unlimited.")
    return process, float(fps)


def command_names(args):
    if not args:
        return []
    hosts = {"wine", "wine64", "wine-preloader", "wine64-preloader"}
    def base(value):
        return ascii_lower(value.replace("\\", "/").rsplit("/", 1)[-1])
    names = [args[0]]
    if base(args[0]) in hosts:
        for arg in args[1:]:
            if base(arg) in hosts:
                continue
            if arg and not arg.startswith("-"):
                names.append(arg)
            break
    return [value.replace("\\", "/").rsplit("/", 1)[-1] for value in names]


def ascii_lower(value):
    return value.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
