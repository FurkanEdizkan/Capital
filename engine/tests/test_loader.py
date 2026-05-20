"""Tests for the strategy plugin loader."""

from pathlib import Path

import pytest

from strategies.builtin import all_strategies, default_strategies
from strategies.loader import load_plugin_strategies

# A well-formed plugin returning one built-in strategy instance.
_GOOD = """
from strategies.ma_cross import MACrossStrategy

def build():
    return [MACrossStrategy("Plugin MA", "SOLUSDT")]
"""

# A plugin whose build() raises.
_RAISES = """
def build():
    raise RuntimeError("boom")
"""

# A plugin whose build() returns something that is not a strategy.
_BAD_RETURN = """
def build():
    return ["not a strategy"]
"""

# A plugin with no build() entrypoint.
_NO_ENTRYPOINT = """
x = 1
"""


def _write(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body)


def test_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert load_plugin_strategies(tmp_path / "does-not-exist") == []


def test_loads_a_valid_plugin(tmp_path: Path) -> None:
    _write(tmp_path, "good.py", _GOOD)
    loaded = load_plugin_strategies(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].name == "Plugin MA"


def test_underscore_files_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "_template.py", _GOOD)
    assert load_plugin_strategies(tmp_path) == []


def test_failing_plugin_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "good.py", _GOOD)
    _write(tmp_path, "boom.py", _RAISES)
    loaded = load_plugin_strategies(tmp_path)
    assert [s.name for s in loaded] == ["Plugin MA"]  # bad one skipped, good one kept


def test_non_strategy_return_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "bad.py", _BAD_RETURN)
    assert load_plugin_strategies(tmp_path) == []


def test_plugin_without_entrypoint_is_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "plain.py", _NO_ENTRYPOINT)
    assert load_plugin_strategies(tmp_path) == []


def test_all_strategies_includes_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, "good.py", _GOOD)
    monkeypatch.setattr("strategies.builtin.settings.strategy_plugins_dir", str(tmp_path))
    names = {s.name for s in all_strategies()}
    assert "Plugin MA" in names
    assert {s.name for s in default_strategies()} <= names


def test_all_strategies_drops_duplicate_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A plugin reusing a built-in strategy name is dropped.
    builtin_name = default_strategies()[0].name
    dup = f"""
from strategies.ma_cross import MACrossStrategy

def build():
    return [MACrossStrategy({builtin_name!r}, "SOLUSDT")]
"""
    _write(tmp_path, "dup.py", dup)
    monkeypatch.setattr("strategies.builtin.settings.strategy_plugins_dir", str(tmp_path))
    assert len(all_strategies()) == len(default_strategies())
