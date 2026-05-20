"""Audit-log helper.

Every config-changing endpoint records an entry here so there is a trail of
who changed what. Phase 6 surfaces these read-only on the History page.
"""

import json
from typing import Any

from sqlmodel import Session

from auth.models import AuditLog


def record_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append an audit entry. `detail` (e.g. before/after values) is JSON-encoded."""
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            target=target,
            detail=json.dumps(detail) if detail is not None else None,
        )
    )
    session.commit()
