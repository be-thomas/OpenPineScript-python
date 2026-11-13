"""`openpinescript` console script: runs the engine CLI with all arguments passed through."""
import subprocess
import sys

from ._runtime import command


def main():
    try:
        argv = command(sys.argv[1:])
    except RuntimeError as e:
        print(f"openpinescript: {e}", file=sys.stderr)
        return 1
    try:
        return subprocess.call(argv)
    except KeyboardInterrupt:
        return 130
    except OSError as e:
        print(f"openpinescript: cannot run Node ({argv[0]}): {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
