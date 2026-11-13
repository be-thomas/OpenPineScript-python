"""Locate the Node executable and the vendored engine."""
import os
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "_engine"
CLI_JS = ENGINE_DIR / "dist" / "cli.mjs"


def node_executable():
    """The Node binary to run: $OPENPINESCRIPT_NODE if set, else the one from nodejs-wheel-binaries."""
    override = os.environ.get("OPENPINESCRIPT_NODE")
    if override:
        return override
    import nodejs_wheel

    root = os.path.dirname(nodejs_wheel.__file__)
    return os.path.join(root, "node.exe") if os.name == "nt" else os.path.join(root, "bin", "node")


def command(args):
    """The full argv for running the engine CLI with `args`."""
    if not CLI_JS.is_file():
        raise RuntimeError(f"vendored engine not found at {CLI_JS}; run scripts/vendor_engine.py")
    return [node_executable(), str(CLI_JS), *[str(a) for a in args]]


def engine_version():
    return (ENGINE_DIR / "VERSION").read_text(encoding="utf-8").strip()

