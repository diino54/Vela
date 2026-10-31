"""Stop the preview automatically if its owning Vela process exits."""
import ctypes
import os
import signal
import sys


def main():
    expected_parent = int(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot set preview parent-death signal')
    if os.getppid() != expected_parent:
        return 1
    os.execv(sys.argv[2], sys.argv[2:])


if __name__ == '__main__':
    sys.exit(main())
