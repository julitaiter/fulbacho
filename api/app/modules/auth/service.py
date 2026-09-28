from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.modules.auth.models import RefreshToken, User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_tokens(db: Session, user: User):
    raw_refresh, refresh_hash, expires_at = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_at=datetime.now(UTC),
        )
    )
    db.flush()
    return create_access_token(user.id), raw_refresh


def register(db: Session, *, email: str, password: str, display_name: str):
    normalized = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing:
        raise ConflictError("Ya existe un usuario con ese email", code="email_already_exists")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
        is_active=True,
    )
    db.add(user)
    db.flush()
    access, refresh = _issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    return user, access, refresh


def login(db: Session, *, email: str, password: str):
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthenticationError("Credenciales inválidas")
    access, refresh = _issue_tokens(db, user)
    db.commit()
    return user, access, refresh


def refresh(db: Session, raw_refresh_token: str):
    token_hash = hash_refresh_token(raw_refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(UTC)
    if not token or token.revoked_at is not None or token.expires_at <= now:
        raise AuthenticationError("Refresh token inválido o vencido")

    user = db.get(User, token.user_id)
    if not user or not user.is_active:
        raise AuthenticationError("Usuario inactivo")

    token.revoked_at = now
    access, new_refresh = _issue_tokens(db, user)
    db.commit()
    return user, access, new_refresh


def logout(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        db.commit()
