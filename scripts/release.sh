#!/usr/bin/env bash
# Build and smoke-test a release. Never uploads: it prints the twine command for the owner.
#   scripts/release.sh            # real release: clean tree, HEAD == origin/main
#   scripts/release.sh --testing  # skip the origin/main check (dry run on a branch)
# Releases vendor the engine from the npm registry only. For a dry run before the engine is
# published, set OPENPINESCRIPT_TEST_TARBALL=/path/to/openpinescript-X.Y.Z.tgz together with --testing.
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
TESTING=0
[ "${1:-}" = "--testing" ] && TESTING=1

if [ -n "$(git status --porcelain)" ]; then
  echo "refusing: working tree is not clean" >&2; exit 1
fi
if [ "$TESTING" = 0 ]; then
  git fetch origin main --quiet
  if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
    echo "refusing: HEAD is not origin/main (merge first, or use --testing for a dry run)" >&2; exit 1
  fi
fi

if [ -n "${OPENPINESCRIPT_TEST_TARBALL:-}" ] && [ "$TESTING" = 0 ]; then
  echo "refusing: OPENPINESCRIPT_TEST_TARBALL only works with --testing" >&2; exit 1
fi

VERSION="$("$PY" -c 'import re;print(re.search(r"^version\s*=\s*\"([^\"]+)\"", open("pyproject.toml").read(), re.M).group(1))')"
# a Python-only release (0.1.1.post1) bundles the engine of its release segment (0.1.1)
ENGINE_VERSION="$(printf '%s' "$VERSION" | sed -E 's/^([0-9]+(\.[0-9]+)*).*/\1/')"
echo "== releasing openpinescript $VERSION (engine $ENGINE_VERSION)"

if [ -n "${OPENPINESCRIPT_TEST_TARBALL:-}" ]; then
  "$PY" scripts/vendor_engine.py "$ENGINE_VERSION" --tarball "$OPENPINESCRIPT_TEST_TARBALL"
else
  "$PY" scripts/vendor_engine.py "$ENGINE_VERSION"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
"$PY" -m venv "$WORK/dev"
"$WORK/dev/bin/pip" -q install build twine pytest pandas
"$WORK/dev/bin/pip" -q install -e .
"$WORK/dev/bin/pytest" -q

rm -rf dist
"$WORK/dev/bin/python" -m build
"$WORK/dev/bin/twine" check dist/*

echo "== smoke test of the built wheel in a fresh venv"
"$PY" -m venv "$WORK/smoke"
"$WORK/smoke/bin/pip" -q install dist/*.whl
S="$WORK/smoke/bin"
cd "$WORK"
cp "$OLDPWD"/tests/data/sma_cross.pine "$OLDPWD"/tests/data/sample.csv .
"$S/openpinescript" sma_cross.pine --data sample.csv 2>/dev/null | grep -q '"bars_processed": 150'
"$S/python" - "$VERSION" <<'PYEOF'
import sys, openpinescript
r = openpinescript.run("sma_cross.pine", "sample.csv")
assert r["bars_processed"] == 150, r
assert openpinescript.__version__.startswith(openpinescript.engine_version())
assert openpinescript.__version__ == sys.argv[1]
print("smoke ok:", openpinescript.__version__)
PYEOF
cd - >/dev/null

echo
echo "Built and verified. Upload (needs your PyPI API token) with:"
echo "  twine upload dist/*"
