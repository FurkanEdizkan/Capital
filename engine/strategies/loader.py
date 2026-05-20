"""Plugin loader — auto-discovers custom code strategies at startup.

An operator drops a Python module into the plugins directory; each module
exposes a `build()` function returning ready-to-run `BaseStrategy` instances.
The loader imports every module, calls `build()`, and returns the combined
list. A plugin that fails to import or build is logged and skipped — one bad
plugin never aborts engine startup.
"""

import importlib.util
import logging
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from strategies.base import BaseStrategy

log = logging.getLogger("capital.strategies.loader")

#: Plugin modules must expose a callable with this name.
ENTRYPOINT = "build"


def _load_module(path: Path) -> ModuleType:
    """Import a standalone .py file as an isolated module."""
    spec = importlib.util.spec_from_file_location(f"capital_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _coerce(result: object, source: str) -> list[BaseStrategy]:
    """Validate that a plugin's build() returned strategy instances."""
    if isinstance(result, BaseStrategy) or not isinstance(result, Iterable):
        raise TypeError(f"{source}: build() must return an iterable of strategies")
    strategies = list(result)
    for item in strategies:
        if not isinstance(item, BaseStrategy):
            raise TypeError(f"{source}: build() yielded a non-strategy: {item!r}")
    return strategies


def load_plugin_strategies(plugins_dir: Path | str) -> list[BaseStrategy]:
    """Import every plugin module in `plugins_dir` and collect its strategies.

    Each `.py` file whose name does not start with `_` must define
    `build() -> Iterable[BaseStrategy]`. Files starting with `_` are treated as
    templates/helpers and skipped. Plugins that fail are logged and skipped.
    """
    directory = Path(plugins_dir)
    if not directory.is_dir():
        log.info("no strategy plugin directory at %s — skipping", directory)
        return []

    discovered: list[BaseStrategy] = []
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            module = _load_module(path)
            entry = getattr(module, ENTRYPOINT, None)
            if not callable(entry):
                log.warning("plugin %s defines no %s() — skipping", path.name, ENTRYPOINT)
                continue
            strategies = _coerce(entry(), path.name)
        except Exception:  # noqa: BLE001 — one bad plugin must not abort startup
            log.exception("plugin %s failed to load — skipping", path.name)
            continue
        log.info("loaded %d strategy(ies) from plugin %s", len(strategies), path.name)
        discovered.extend(strategies)
    return discovered
