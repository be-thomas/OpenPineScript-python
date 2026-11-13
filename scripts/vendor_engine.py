#!/usr/bin/env python3
"""Vendor the openpinescript npm release into src/openpinescript/_engine/.

    python scripts/vendor_engine.py 0.1.1
    python scripts/vendor_engine.py 0.1.1 --tarball path/to/openpinescript-0.1.1.tgz   # testing only

Downloads the exact npm tarball, checks its sha512 against the registry's
`dist.integrity`, and extracts dist/cli.mjs. cli.mjs imports `antlr4ng` (the engine's
only dependency) as a bare module, so antlr4ng is vendored next to it under
_engine/node_modules/ with the same integrity check. The antlr4ng version is the highest
one the engine's package.json range allows (what `npm install` would pick), so the
result matches what npx users get. No network is needed at runtime.

--tarball vendors the engine from a local tarball (for testing before it is published):
the engine's registry integrity check is skipped, with a warning. Releases never use it.
"""
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

REGISTRY = "https://registry.npmjs.org"
ENGINE_DIR = Path(__file__).resolve().parent.parent / "src" / "openpinescript" / "_engine"


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def parse_version(v):
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", v)
    return tuple(int(x) for x in m.groups()) if m else None


def resolve_range(spec, versions):
    """Highest release (no prereleases) in `versions` satisfying an exact, ^ or ~ range."""
    m = re.fullmatch(r"([\^~]?)(\d+\.\d+\.\d+)", spec)
    if not m:
        raise SystemExit(f"unsupported dependency range {spec!r} (only exact, ^ and ~ are handled)")
    op, base = m.group(1), parse_version(m.group(2))
    if op == "":
        upper = None
    elif op == "~" or (op == "^" and base[0] == 0 and base[1] != 0):
        upper = (base[0], base[1] + 1, 0) if op == "~" else (0, base[1] + 1, 0)
    elif op == "^" and base[0] == 0:
        upper = (0, 0, base[2] + 1)
    else:
        upper = (base[0] + 1, 0, 0)
    ok = []
    for v in versions:
        t = parse_version(v)
        if t is None:
            continue
        if (t == base) if upper is None else (base <= t < upper):
            ok.append(t)
    if not ok:
        raise SystemExit(f"no published version satisfies {spec!r}")
    return ".".join(map(str, max(ok)))


def fetch_package(name, version):
    """Download name@version from npm and return the verified tarball as a TarFile."""
    meta = json.loads(fetch(f"{REGISTRY}/{name}/{version}"))
    algo, _, expected = meta["dist"]["integrity"].partition("-")
    if algo != "sha512":
        raise SystemExit(f"{name}@{version}: unexpected integrity algorithm {algo!r}")
    blob = fetch(meta["dist"]["tarball"])
    actual = base64.b64encode(hashlib.sha512(blob).digest()).decode()
    if actual != expected:
        raise SystemExit(f"{name}@{version}: sha512 mismatch (registry {expected}, downloaded {actual})")
    print(f"verified {name}@{version} sha512 ({len(blob)} bytes)")
    return tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz"), meta


def extract(tar, wanted, dest):
    """Extract regular files under package/<wanted...> into dest (not .d.ts/.map), refusing odd paths."""
    dest.mkdir(parents=True, exist_ok=True)
    for m in tar.getmembers():
        rel = m.name.split("/", 1)[1] if "/" in m.name else ""
        if not m.isfile() or ".." in rel.split("/") or rel.endswith((".d.ts", ".map")):
            continue
        if any(rel == w or rel.startswith(w + "/") for w in wanted):
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(m).read())


def main():
    args = sys.argv[1:]
    tarball = None
    if "--tarball" in args:
        i = args.index("--tarball")
        if i + 1 >= len(args):
            raise SystemExit(__doc__)
        tarball = args[i + 1]
        del args[i : i + 2]
    if len(args) != 1:
        raise SystemExit(__doc__)
    version = args[0]

    if tarball:
        print(f"WARNING: vendoring the engine from {tarball}; its integrity is NOT checked against the registry")
        engine_tar = tarfile.open(tarball, mode="r:gz")
        meta = json.load(engine_tar.extractfile("package/package.json"))
        if meta.get("version") != version:
            raise SystemExit(f"tarball is openpinescript {meta.get('version')}, not {version}")
    else:
        engine_tar, meta = fetch_package("openpinescript", version)
    deps = meta.get("dependencies", {})
    if set(deps) != {"antlr4ng"}:
        raise SystemExit(f"engine dependencies changed ({deps}); update this script before vendoring")
    all_versions = json.loads(fetch(f"{REGISTRY}/antlr4ng"))["versions"]
    antlr_version = resolve_range(deps["antlr4ng"], all_versions)
    print(f"antlr4ng {deps['antlr4ng']} resolves to {antlr_version}")
    antlr_tar, _ = fetch_package("antlr4ng", antlr_version)

    if ENGINE_DIR.exists():
        shutil.rmtree(ENGINE_DIR)
    extract(engine_tar, ["dist/cli.mjs", "LICENSE", "package.json"], ENGINE_DIR)
    extract(antlr_tar, ["dist", "package.json", "LICENSE.txt"], ENGINE_DIR / "node_modules" / "antlr4ng")
    (ENGINE_DIR / "VERSION").write_text(version + "\n", encoding="utf-8")
    print(f"vendored openpinescript {version} (+ antlr4ng {antlr_version}) into {ENGINE_DIR}")


if __name__ == "__main__":
    main()
