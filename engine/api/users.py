"""User management endpoints — admin only (see plan: Authentication & Roles)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import Role, User
from auth.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

AdminUser = Annotated[User, Depends(require_admin)]


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.user


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


def _read(u: User) -> UserRead:
    assert u.id is not None
    return UserRead(id=u.id, username=u.username, role=u.role, is_active=u.is_active)


@router.get("", response_model=list[UserRead])
def list_users(_: AdminUser, session: SessionDep) -> list[UserRead]:
    users = session.exec(select(User).order_by(User.username)).all()
    return [_read(u) for u in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, admin: AdminUser, session: SessionDep) -> UserRead:
    if session.exec(select(User).where(User.username == body.username)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role.value,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    record_audit(
        session,
        actor=admin.username,
        action="user.create",
        target=user.username,
        detail={"role": user.role},
    )
    return _read(user)


def _get_or_404(session: SessionDep, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, body: UserUpdate, admin: AdminUser, session: SessionDep
) -> UserRead:
    user = _get_or_404(session, user_id)
    changes: dict[str, object] = {}
    if body.role is not None:
        changes["role"] = {"from": user.role, "to": body.role.value}
        user.role = body.role.value
    if body.is_active is not None:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
    if changes:
        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        session.refresh(user)
        record_audit(
            session,
            actor=admin.username,
            action="user.update",
            target=user.username,
            detail=changes,
        )
    return _read(user)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int, body: PasswordReset, admin: AdminUser, session: SessionDep
) -> None:
    user = _get_or_404(session, user_id)
    user.password_hash = hash_password(body.password)
    user.updated_at = datetime.now(UTC)
    session.add(user)
    session.commit()
    record_audit(
        session, actor=admin.username, action="user.password_reset", target=user.username
    )
