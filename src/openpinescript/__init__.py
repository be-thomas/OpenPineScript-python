"""Run TradingView Pine Script locally: a thin wrapper over the openpinescript engine."""
import json
import os
import re
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version as _dist_version

from ._runtime import command, engine_version

try:
    __version__ = _dist_version("openpinescript")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"

__all__ = ["run", "OpenPineScriptError", "engine_version", "__version__"]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_CSV_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


class OpenPineScriptError(Exception):
    """The engine CLI failed. `returncode` is its exit code (None on timeout), `stderr` its error text."""

    def __init__(self, message, returncode=None, stderr=""):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def _write_csv(df, path):
    import pandas as pd

    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "time" not in df.columns:
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame needs a 'time' column or a DatetimeIndex")
        df.insert(0, "time", df.index)
    if "volume" not in df.columns:
        df["volume"] = 0
    missing = [c for c in _CSV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing columns: {', '.join(missing)}")
    df = df[_CSV_COLUMNS]
    if pd.api.types.is_numeric_dtype(df["time"]):
        raise ValueError("'time' must be datetimes or ISO 8601 strings, not epoch numbers")
    # The engine reads the time with JavaScript's `new Date(...)`; ISO 8601 UTC is safe.
    t = pd.to_datetime(df["time"])
    if t.dt.tz is not None:
        t = t.dt.tz_convert("UTC").dt.tz_localize(None)
    df["time"] = t.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df.to_csv(path, index=False)


def _invoke(args, timeout):
    try:
        p = subprocess.run(command(args), capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise OpenPineScriptError(f"timed out after {timeout}s", None, "") from e
    except (OSError, RuntimeError) as e:
        raise OpenPineScriptError(f"cannot run the engine: {e}", None, "") from e
    if p.returncode != 0:
        stderr = _ANSI.sub("", p.stderr).strip()
        lines = [l for l in stderr.splitlines() if l.strip() and not l.startswith(("Compiling:", "Pine Script:", "Running backtest"))]
        first = lines[0] if lines else "no error output"
        raise OpenPineScriptError(f"openpinescript exited with code {p.returncode}: {first}", p.returncode, stderr)
    return p


def run(script, data, *, inputs=None, out_dir=None, extra_args=None, timeout=None):
    """Run a Pine script against OHLCV data and return the CLI's JSON result as a dict.

    script     path to a .pine file, or Pine source text (anything containing a newline, or
               a string that is not an existing file)
    data       path to a CSV (time,open,high,low,close,volume) or a pandas DataFrame
    inputs     {"input_0": 5} overrides input()s, like `--input input_0=5`; bools become 1/0
    out_dir    also write chart.csv, trades.csv and summary.json there (the result then
               gains a "files" list of the paths written)
    extra_args more CLI flags, passed through as given
    timeout    seconds before the run is abandoned
    """
    with tempfile.TemporaryDirectory(prefix="openpinescript-") as tmp:
        if isinstance(script, os.PathLike) or (
            isinstance(script, str) and "\n" not in script and os.path.isfile(script)
        ):
            script_path = os.fspath(script)
            if not script_path.endswith(".pine"):  # the CLI picks the script by its .pine suffix
                src = os.path.join(tmp, "script.pine")
                with open(script_path, "rb") as f, open(src, "wb") as g:
                    g.write(f.read())
                script_path = src
        elif isinstance(script, str):
            script_path = os.path.join(tmp, "script.pine")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
        else:
            raise TypeError("script must be a path or Pine source text")

        if isinstance(data, (str, os.PathLike)):
            data_path = os.fspath(data)
        else:
            data_path = os.path.join(tmp, "data.csv")
            _write_csv(data, data_path)

        args = [script_path, "--data", data_path]
        for key, value in (inputs or {}).items():
            if isinstance(value, bool):
                value = int(value)
            args += ["--input", f"{key}={value}"]
        args += [str(a) for a in (extra_args or [])]

        stdout = _invoke(args, timeout).stdout
        try:
            result = json.loads(stdout)
        except ValueError as e:
            raise OpenPineScriptError(
                "the CLI did not print JSON (do extra_args include an --out-* flag?)", 0, stdout[:500]
            ) from e

        if out_dir is not None:
            out_dir = os.fspath(out_dir)
            # With any --out-* flag the CLI prints file confirmations instead of JSON,
            # so the files come from a second run.
            _invoke(args + ["--out-dir", out_dir], timeout)
            result["files"] = sorted(
                os.path.join(out_dir, n) for n in os.listdir(out_dir) if n in ("chart.csv", "trades.csv", "summary.json")
            )
        return result
