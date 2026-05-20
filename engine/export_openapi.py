"""Export the engine's OpenAPI schema to web/openapi.json.

The schema is the single source of truth for the web client's types — the
`web` app generates its typed REST client from this file. CI re-runs this and
fails on drift, so the committed schema always matches the API.

Usage:  uv run python export_openapi.py
"""

import json
from pathlib import Path

from main import app

OUTPUT = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def export() -> Path:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    return OUTPUT


if __name__ == "__main__":
    print(f"wrote {export()}")
