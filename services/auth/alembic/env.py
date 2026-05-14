from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool

from alembic import context

from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

# Custom Change: load .env from services/auth/
load_dotenv()

AUTH_DB_URL = (
    f"postgresql+psycopg://"
    f"{os.environ['AUTH_DB_USER']}:{os.environ['AUTH_DB_PASSWORD']}"
    f"@{os.environ['AUTH_DB_HOST']}:{os.environ['POSTGRES_PORT']}"
    f"/{os.environ['AUTH_DB_NAME']}"
)

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Inject the database URL so Alembic internals can reference it if needed.
config.set_main_option("sqlalchemy.url", AUTH_DB_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Model metadata (for autogenerate support)
# ---------------------------------------------------------------------------

from src import model
print("model imported:", model)
print("metadata tables:", model.AuthBase.metadata.tables)
target_metadata = model.AuthBase.metadata

# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    context.configure(
        url=AUTH_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        AUTH_DB_URL,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()