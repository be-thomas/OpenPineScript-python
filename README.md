# openpinescript

Run TradingView Pine Script (v1 to v6) locally and offline. It compiles your script to JavaScript and runs it on your own OHLCV candles: indicators, plots and strategy backtests, with no TradingView account and no network.

This package is a thin Python wrapper over the [`openpinescript`](https://github.com/be-thomas/OpenPineScript) npm engine. Its version always matches the engine release it bundles (`openpinescript 0.1.1` bundles engine `0.1.1`; a Python-only fix is released as `0.1.1.postN`). Node.js is bundled too (through [`nodejs-wheel-binaries`](https://pypi.org/project/nodejs-wheel-binaries/)), so you do not need Node or npm installed.

```
pip install openpinescript
pip install "openpinescript[pandas]"   # to pass pandas DataFrames
```

Requires Python 3.9 or newer. Docs for the engine, the Pine features it supports and the full CLI reference: https://be-thomas.github.io/OpenPineScript/

## Command line

The `openpinescript` command passes every argument to the engine CLI and gives the same stdout, stderr and exit code as `npx openpinescript`.

```
openpinescript sma_cross.pine --data sample.csv --out-dir results
```

```
Compiling: sma_cross.pine...
Pine Script: v5
Running backtest: 150 bars...
✔ Done.
✔ Chart    → results/chart.csv
✔ Trades   → results/trades.csv  (3 trades)
✔ Summary  → results/summary.json

=== sma_cross.pine — Summary ===
Bars processed : 150
Plots recorded : 2

Performance:
  Net Profit         $-279.00 (-0.28%)
  Total Trades       3
  Win Rate           33.3%  (1W / 2L)
  Profit Factor      0.179
  Max Drawdown       0.34%
  Avg Win / Avg Loss $61.00 / $170.00

Script Inputs:
  input_0  "Fast Length"  [integer]  = 9 (default)
  input_1  "Slow Length"  [integer]  = 21 (default)
  Tip: override with --input input_0=<value>
```

The CSV has one bar per row, oldest first, with columns `time,open,high,low,close,volume` (ISO 8601 or `YYYY-MM-DD` times). With no `--out-*` flag the result is printed to stdout as JSON. See the [CLI guide](https://be-thomas.github.io/OpenPineScript/cli.md) for every flag.

## Python

```python
import openpinescript

result = openpinescript.run("sma_cross.pine", "sample.csv", inputs={"input_0": 5, "input_1": 30})
print(result["bars_processed"])   # 150
print(result["performance"])
```

```
150
{'net_profit': -1396, 'net_profit_percent': -1.4, 'gross_profit': 0, 'gross_loss': 1396, 'total_closed_trades': 3, 'winning_trades': 0, 'losing_trades': 3, 'win_rate': 0, 'avg_win': 0, 'avg_loss': 465.33, 'profit_factor': 0, 'max_drawdown_percent': 1.4}
```

`run(script, data, *, inputs=None, out_dir=None, extra_args=None, timeout=None)` returns the CLI's JSON result as a dict (`script`, `bars_processed`, `inputs`, `performance`; `performance` is `None` for an indicator).

- `script` is a path to a `.pine` file, or Pine source text.
- `data` is a CSV path or a pandas DataFrame with `time`, `open`, `high`, `low`, `close` and (optionally) `volume` columns; a `DatetimeIndex` works in place of `time`.
- `inputs={"input_0": 5}` overrides `input()` calls (`--input input_0=5`). Booleans are sent as 1 or 0.
- `out_dir` also writes `chart.csv`, `trades.csv` and `summary.json` there and adds a `"files"` list to the result.
- `extra_args` are more CLI flags, and `timeout` is in seconds.

```python
import pandas as pd, openpinescript

df = pd.read_csv("sample.csv", parse_dates=["time"])
openpinescript.run('//@version=5\nindicator("x")\nplot(close)\n', df)["bars_processed"]   # 150
```

A failing run raises `OpenPineScriptError`, with `.returncode` and `.stderr`:

```python
try:
    openpinescript.run("broken.pine", "sample.csv")
except openpinescript.OpenPineScriptError as e:
    print(e.returncode)   # 1
    print(e.stderr)
```

```
1
Compiling: broken.pine...
Transpilation failed: Pine Script v5: parsing failed with 1 error(s)
  [Line 4:0] The script ends in the middle of a statement at line 3 — was it pasted completely? (missing ')' at '<EOF>')
```

`openpinescript.__version__` is the package version and `openpinescript.engine_version()` the bundled engine version.

## Notes

- The engine, not this wrapper, defines behaviour: `openpinescript --help` prints usage to stdout and exits 0; a missing script or `--data` prints usage to stderr and exits 1, exactly like `npx openpinescript`.
- Set `OPENPINESCRIPT_NODE=/path/to/node` to use a different Node (20 or newer) than the bundled one.

## License

GPL-3.0-or-later, the same as the engine.
