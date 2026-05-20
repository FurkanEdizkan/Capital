"""Seed the initial admin operator on first startup.

If the `user` table is empty, create an admin from CAPITAL_ADMIN_USERNAME /
CAPITAL_ADMIN_PASSWORD. The operator should change this password immediately.
"""

import logging

from sqlmodel import Session, select

from auth.models import Role, User
from auth.security import hash_password
from config import settings
from db import engine

log = logging.getLogger("capital.auth.seed")


def seed_admin() -> None:
    with Session(engine) as session:
        existing = session.exec(select(User)).first()
        if existing is not None:
            return
        admin = User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role=Role.admin.value,
        )
        session.add(admin)
        session.commit()
        log.warning(
            "Seeded admin operator '%s' — change this password immediately.",
            settings.admin_username,
        )
