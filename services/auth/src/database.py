"""Database engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

# Single engine instance shared across the app.
# pool_pre_ping=True checks connections before use, avoiding stale connection errors.
_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)

# Session factory — calling SessionLocal() creates a new session.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    Usage:
        @router.get("/users")
        def list_users(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()