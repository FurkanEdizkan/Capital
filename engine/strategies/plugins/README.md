# Strategy plugins

Drop a Python module in this directory to add a custom code strategy without
touching the engine. On startup the engine scans this folder and loads every
`.py` file whose name does **not** start with `_`.

## Contract

Each plugin module must define a `build()` function:

```python
def build() -> list[BaseStrategy]:
    ...
```

`build()` returns ready-to-run `BaseStrategy` instances. A plugin may define
its own `BaseStrategy` subclass (see [`_example.py`](_example.py)) or return
configured instances of the built-in strategy types.

## Rules

- Files starting with `_` (like `_example.py`) are treated as templates and
  are **not** loaded.
- Strategy `name`s must be unique across all built-ins and plugins — the
  loader drops duplicates and logs a warning.
- A plugin that raises on import or in `build()` is logged and skipped; it
  never aborts engine startup.

The scanned directory is configurable via `CAPITAL_STRATEGY_PLUGINS_DIR`.
