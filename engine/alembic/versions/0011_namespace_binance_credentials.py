"""rename Binance credential keys into the venue:* namespace

Credentials are now stored per-venue under `venue:{venue}:{field}` keys
(see appsettings.store). This renames the two existing Binance rows so
stored keys survive the change without re-entry.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-21 20:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# old key -> new namespaced key
_RENAMES: dict[str, str] = {
    "binance_api_key": "venue:binance:api_key",
    "binance_api_secret": "venue:binance:api_secret",
}

_UPDATE = sa.text("UPDATE setting SET key = :new WHERE key = :old")


def upgrade() -> None:
    for old, new in _RENAMES.items():
        op.get_bind().execute(_UPDATE, {"old": old, "new": new})


def downgrade() -> None:
    for old, new in _RENAMES.items():
        op.get_bind().execute(_UPDATE, {"old": new, "new": old})
