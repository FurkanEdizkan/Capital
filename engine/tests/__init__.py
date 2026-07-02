"""Marks `tests` as a regular package.

Several Polymarket dependencies (py-clob-client, py-order-utils,
py-builder-signing-sdk) ship a stray top-level `tests` package into
site-packages. Without this `__init__.py` the engine's own tests directory is
only a namespace package, which loses import resolution to that regular
package and breaks `from tests.conftest import ...`.
"""
