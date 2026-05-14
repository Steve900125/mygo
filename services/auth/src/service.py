"""Auth service: user creation, login, password update."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.model import User
from src.schema import PasswordUpdate, UserCreate, UserLogin

# Password hasher (argon2 by default via pwdlib[argon2])
_password_hash = PasswordHash.recommended()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class CreateUserResult(str, Enum):
    """Outcome of a create_user call."""
    SUCCESS = "success"
    USER_EXISTS = "user_exists"


class LoginFailReason(str, Enum):
    """Reason for a failed login. Hidden from end users."""
    USER_NOT_FOUND = "user_not_found"
    WRONG_PASSWORD = "wrong_password"


@dataclass
class LoginResult:
    """Login outcome. token is set on success; reason is set on failure."""
    success: bool
    token: str | None = None
    reason: LoginFailReason | None = None


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------

def create_user(db: Session, data: UserCreate) -> CreateUserResult:
    """Create a new user with hashed password.

    Args:
        db: SQLAlchemy session.
        data: Validated user creation payload.

    Returns:
        CreateUserResult.SUCCESS or CreateUserResult.USER_EXISTS.
    """
    existing = db.scalar(
        select(User).where(User.account_name == data.account_name)
    )
    if existing is not None:
        return CreateUserResult.USER_EXISTS

    user = User(
        account_name=data.account_name,
        password=_password_hash.hash(data.password),
    )
    db.add(user)
    db.commit()
    return CreateUserResult.SUCCESS


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login(db: Session, data: UserLogin) -> LoginResult:
    """Verify credentials and return a JWT on success.

    Args:
        db: SQLAlchemy session.
        data: Validated login payload.

    Returns:
        LoginResult with success flag, token (on success), and reason (on failure).
        The reason should NOT be exposed to clients to prevent user enumeration.
    """
    user = db.scalar(
        select(User).where(User.account_name == data.account_name)
    )
    if user is None:
        return LoginResult(success=False, reason=LoginFailReason.USER_NOT_FOUND)

    if not _password_hash.verify(data.password, user.password):
        return LoginResult(success=False, reason=LoginFailReason.WRONG_PASSWORD)

    token = _create_access_token(user.id)
    return LoginResult(success=True, token=token)


# ---------------------------------------------------------------------------
# Password update
# ---------------------------------------------------------------------------

def update_password(db: Session, user_id: int, data: PasswordUpdate) -> bool:
    """Update password after verifying the old one.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user id (from JWT).
        data: Validated password update payload.

    Returns:
        True if updated, False if old password was wrong or user not found.
    """
    user = db.get(User, user_id)
    if user is None:
        return False

    if not _password_hash.verify(data.old_password, user.password):
        return False

    user.password = _password_hash.hash(data.new_password)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _create_access_token(user_id: int) -> str:
    """Sign a short-lived JWT containing the user id."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Decode a JWT and return user_id, or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None