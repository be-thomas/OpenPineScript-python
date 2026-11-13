import json
import subprocess
import sys
from pathlib import Path

import pytest

import openpinescript
from openpinescript import OpenPineScriptError, run

DATA = Path(__file__).parent / "data"
CSV = DATA / "sample.csv"
SMA = DATA / "sma_cross.pine"
BROKEN = DATA / "broken.pine"


def cli(*args):
    return subprocess.run([sys.executable, "-m", "openpinescript", *map(str, args)], capture_output=True, text=True)


def test_versions():
    assert openpinescript.engine_version() == "0.2.0"
    assert openpinescript.__version__.startswith("0.2.0")


def test_cli_help():
    for flag in ("--help", "-h"):
        p = cli(flag)
        assert p.returncode == 0
        assert "Usage" in p.stdout
        assert "--data" in p.stdout


def test_cli_missing_data_exits_1():
    p = cli(SMA)
    assert p.returncode == 1
    assert "--data" in p.stderr and "Usage" in p.stderr


def test_cli_run_prints_json():
    p = cli(SMA, "--data", CSV)
    assert p.returncode == 0
    assert json.loads(p.stdout)["bars_processed"] == 150


def test_cli_broken_script_exits_1():
    p = cli(BROKEN, "--data", CSV)
    assert p.returncode == 1
    assert "Transpilation failed" in p.stderr
    assert p.stdout == ""


def test_run_with_path():
    r = run(SMA, CSV)
    assert r["script"] == "sma_cross.pine"
    assert r["bars_processed"] == 150
    assert [i["id"] for i in r["inputs"]] == ["input_0", "input_1"]
    assert r["performance"] is not None


def test_run_with_str_path():
    assert run(str(SMA), str(CSV))["script"] == "sma_cross.pine"


def test_run_with_source_text():
    src = '//@version=5\nindicator("x")\nplot(close)\n'
    r = run(src, CSV)
    assert r["bars_processed"] == 150
    assert r["performance"] is None


def test_run_with_dataframe():
    pd = pytest.importorskip("pandas")
    df = pd.read_csv(CSV, parse_dates=["time"])
    assert run(SMA, df) == run(SMA, CSV)
    # DatetimeIndex, upper-case columns and no volume are accepted too
    df2 = df.set_index("time").drop(columns="volume")
    df2.columns = [c.upper() for c in df2.columns]
    assert run(SMA, df2)["bars_processed"] == 150


def test_dataframe_missing_columns():
    pd = pytest.importorskip("pandas")
    with pytest.raises(ValueError, match="missing columns"):
        run(SMA, pd.DataFrame({"time": ["2020-01-01"], "close": [1.0]}))


def test_inputs_mapping():
    r = run(SMA, CSV, inputs={"input_0": 5, "input_1": 30})
    by_id = {i["id"]: i for i in r["inputs"]}
    assert by_id["input_0"]["current"] == 5 and by_id["input_0"]["overridden"]
    assert by_id["input_1"]["current"] == 30 and by_id["input_1"]["overridden"]
    assert run(SMA, CSV)["inputs"][0]["overridden"] is False


def test_extra_args_dry_run():
    assert run(SMA, CSV, extra_args=["--dry-run"])["bars_processed"] == 1


def test_out_dir(tmp_path):
    out = tmp_path / "results"
    r = run(SMA, CSV, out_dir=out)
    names = {Path(f).name for f in r["files"]}
    assert "chart.csv" in names and "summary.json" in names
    assert (out / "chart.csv").read_text().startswith("time,open,high,low,close,volume,Fast,Slow")


def test_error_raising():
    with pytest.raises(OpenPineScriptError) as e:
        run(BROKEN, CSV)
    assert e.value.returncode == 1
    assert "Transpilation failed" in e.value.stderr
    assert "\x1b" not in e.value.stderr


def test_error_missing_data():
    with pytest.raises(OpenPineScriptError) as e:
        run(SMA, DATA / "nope.csv")
    assert "Cannot read CSV" in e.value.stderr


def test_error_not_json(tmp_path):
    with pytest.raises(OpenPineScriptError):
        run(SMA, CSV, extra_args=["--out-summary", str(tmp_path / "s.json")])  # any --out-* flag suppresses the JSON
