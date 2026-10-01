import os
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import normalize_email


def bootstrap_superuser(db: Session, environ: Mapping[str, str] | None = None) -> str:
    """Create/promote only; never reset credentials or reactivate existing users."""
    env = os.environ if environ is None else environ
    email = env.get("BOOTSTRAP_SUPERUSER_EMAIL", "").strip()
    password = env.get("BOOTSTRAP_SUPERUSER_PASSWORD", "")
    name = env.get("BOOTSTRAP_SUPERUSER_NAME", "").strip()
    if not email or not password or not name:
        return "skipped"
    # Reuse registration validation without exposing invalid passwords in errors.
    try:
        payload = RegisterRequest(email=email, password=password, display_name=name)
    except ValueError:
        raise ValueError("Invalid bootstrap variables; check email, password length and name.") from None
    email = normalize_email(str(payload.email))
    # Serialize concurrent deploys for this email, including the first insert.
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(email))))
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user is None:
        db.add(User(
            email=email, display_name=payload.display_name.strip(),
            password_hash=hash_password(payload.password), is_active=True, is_superuser=True,
        ))
        outcome = "created"
    elif not user.is_superuser:
        user.is_superuser = True
        outcome = "promoted"
    else:
        outcome = "unchanged"
    db.commit()
    return outcome
