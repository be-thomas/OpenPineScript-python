# Contributing

This package is a wrapper: all behaviour lives in the [engine](https://github.com/be-thomas/OpenPineScript). The Python package version is always the same as the npm `openpinescript` release it bundles.

## Bumping the version with an npm release

1. Publish the new engine to npm first.
2. Change `version` in `pyproject.toml` to the npm version, and the expected version in `tests/test_openpinescript.py` (`test_versions`).
3. Merge to `main`, then run `scripts/release.sh`. It vendors that exact npm tarball (sha512 checked against the registry), runs the tests, builds the sdist and wheel, smoke-tests the wheel in a fresh venv, and prints the `twine upload` command. It never uploads; the owner runs that with a PyPI API token.

If the engine's dependencies change, `scripts/vendor_engine.py` stops and must be updated. It reads the engine's `package.json`, resolves the `antlr4ng` range (exact, `^` or `~` only) to the highest published version and vendors it next to the CLI, checking integrity.

A Python-only fix that does not change the engine is a PEP 440 post release: `0.1.1.post1` bundles engine `0.1.1`. The build hook and `scripts/release.sh` compare the engine `VERSION` with the release segment of the package version.

To try a release before the engine is on npm, vendor from a local tarball: `python scripts/vendor_engine.py 0.1.1 --tarball path/to/openpinescript-0.1.1.tgz` (its integrity is not checked). `scripts/release.sh` itself only vendors from the registry; for a dry run use `OPENPINESCRIPT_TEST_TARBALL=path scripts/release.sh --testing`.

## Development

```
python -m venv .venv && . .venv/bin/activate
python scripts/vendor_engine.py 0.1.1     # fills the git-ignored src/openpinescript/_engine/
pip install -e ".[pandas]" pytest
pytest
```

Building fails with a clear message if `_engine/` is missing or does not match the package version.
