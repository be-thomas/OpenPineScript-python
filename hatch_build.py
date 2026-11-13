"""Build hook: refuse to build a package that does not contain the vendored engine."""
import os
import re

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class EngineCheckHook(BuildHookInterface):
    def initialize(self, version, build_data):
        engine = os.path.join(self.root, "src", "openpinescript", "_engine")
        needed = [
            os.path.join(engine, "VERSION"),
            os.path.join(engine, "dist", "cli.mjs"),
            os.path.join(engine, "node_modules", "antlr4ng", "dist", "index.mjs"),
        ]
        missing = [p for p in needed if not os.path.isfile(p)]
        if missing:
            raise RuntimeError(
                "The vendored engine is missing (" + ", ".join(os.path.relpath(p, self.root) for p in missing)
                + "). Run `python scripts/vendor_engine.py " + re.match(r"\d+(\.\d+)*", self.metadata.version).group(0) + "` first."
            )
        with open(os.path.join(engine, "VERSION"), encoding="utf-8") as f:
            engine_version = f.read().strip()
        # A Python-only release (0.1.1.post1) bundles the same engine as its release segment (0.1.1).
        release = re.match(r"\d+(\.\d+)*", self.metadata.version).group(0)
        if engine_version != release:
            raise RuntimeError(
                f"Vendored engine is {engine_version} but the package version is {self.metadata.version}. "
                f"Run `python scripts/vendor_engine.py {release}`."
            )
