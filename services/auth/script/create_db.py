"""IAM Database Provisioning: Assign a database and user to the auth service.

This script uses admin credentials to:
  1. Create the auth database (idempotent, skips if exists).
  2. Create the auth user (idempotent, skips if exists).
  3. Grant database-level CONNECT privilege.
  4. Grant full schema-level privileges inside the auth database, wrapped in a
     transaction so that a partial failure leaves no dangling state.

Usage:
    Fill in the required variables in your .env file, then run:

        python create_auth_db.py

Required .env variables:
    POSTGRES_USER       Admin username.
    POSTGRES_PASSWORD   Admin password.
    POSTGRES_HOST       Database host.
    POSTGRES_PORT       Database port (default: 5432).
    POSTGRES_DB         Admin database (used for the initial connection).
    AUTH_DB_USER        Username to create for the auth service.
    AUTH_DB_PASSWORD    Password for the auth service user.
    AUTH_DB_NAME        Database name to create for the auth service.
"""

import logging
import os
import sys

import psycopg
from psycopg import sql
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    """Return the value of an environment variable or abort if it is missing.

    Args:
        key: The environment variable name.

    Returns:
        The non-empty string value of the variable.

    Raises:
        SystemExit: If the variable is missing or empty.
    """
    value = os.environ.get(key, "").strip()
    if not value:
        logger.error("Required environment variable '%s' is not set.", key)
        sys.exit(1)
    return value


def load_config() -> dict[str, str]:
    """Load and validate all required environment variables.

    Returns:
        A dict mapping config keys to their string values.
    """
    load_dotenv()
    return {
        "admin_user":      _require_env("POSTGRES_USER"),
        "admin_password":  _require_env("POSTGRES_PASSWORD"),
        "admin_host":      _require_env("POSTGRES_HOST"),
        "admin_port":      _require_env("POSTGRES_PORT"),
        "admin_db":        _require_env("POSTGRES_DB"),
        "auth_db_user":    _require_env("AUTH_DB_USER"),
        "auth_db_password": _require_env("AUTH_DB_PASSWORD"),
        "auth_db_name":    _require_env("AUTH_DB_NAME"),
    }


# ---------------------------------------------------------------------------
# Step 1 — Create database and user (must run with autocommit=True)
# ---------------------------------------------------------------------------

def _user_exists(cur: psycopg.Cursor, username: str) -> bool:
    """Check whether a PostgreSQL role already exists.

    Args:
        cur: An open cursor connected to any database.
        username: The role name to look up.

    Returns:
        True if the role exists, False otherwise.
    """
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
    return cur.fetchone() is not None


def _database_exists(cur: psycopg.Cursor, db_name: str) -> bool:
    """Check whether a PostgreSQL database already exists.

    Args:
        cur: An open cursor connected to any database.
        db_name: The database name to look up.

    Returns:
        True if the database exists, False otherwise.
    """
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    return cur.fetchone() is not None


def provision_database_and_user(cfg: dict[str, str]) -> None:
    """Create the auth database and user, then grant CONNECT.

    CREATE DATABASE and CREATE USER cannot run inside a transaction block in
    PostgreSQL, so this function uses autocommit=True.  Each statement is
    guarded by an existence check to make the whole step idempotent.

    Uses psycopg.sql.Identifier / Literal throughout so that all names and
    values are safely quoted — no SQL injection risk even if .env values
    contain special characters.

    Args:
        cfg: Config dict produced by :func:`load_config`.
    """
    logger.info("Connecting to admin database '%s'.", cfg["admin_db"])

    # autocommit=True is REQUIRED for CREATE DATABASE / CREATE USER.
    with psycopg.connect(
        host=cfg["admin_host"],
        port=int(cfg["admin_port"]),
        user=cfg["admin_user"],
        password=cfg["admin_password"],
        dbname=cfg["admin_db"],
        connect_timeout=5,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:

            # -- Create user ------------------------------------------------
            if _user_exists(cur, cfg["auth_db_user"]):
                logger.info(
                    "User '%s' already exists — skipping CREATE USER.",
                    cfg["auth_db_user"],
                )
            else:
                logger.info("Creating user '%s'.", cfg["auth_db_user"])
                cur.execute(
                    sql.SQL("CREATE USER {user} WITH PASSWORD {password}").format(
                        user=sql.Identifier(cfg["auth_db_user"]),
                        # sql.Literal adds single quotes and escapes special chars
                        password=sql.Literal(cfg["auth_db_password"]),
                    )
                )
                logger.info("User '%s' created.", cfg["auth_db_user"])

            # -- Create database --------------------------------------------
            if _database_exists(cur, cfg["auth_db_name"]):
                logger.info(
                    "Database '%s' already exists — skipping CREATE DATABASE.",
                    cfg["auth_db_name"],
                )
            else:
                logger.info("Creating database '%s'.", cfg["auth_db_name"])
                cur.execute(
                    sql.SQL("CREATE DATABASE {db} OWNER {user}").format(
                        db=sql.Identifier(cfg["auth_db_name"]),
                        user=sql.Identifier(cfg["auth_db_user"]),
                    )
                )
                logger.info("Database '%s' created.", cfg["auth_db_name"])

            # -- Grant CONNECT (idempotent in PostgreSQL) -------------------
            logger.info(
                "Granting CONNECT on '%s' to '%s'.",
                cfg["auth_db_name"],
                cfg["auth_db_user"],
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {db} TO {user}").format(
                    db=sql.Identifier(cfg["auth_db_name"]),
                    user=sql.Identifier(cfg["auth_db_user"]),
                )
            )

    logger.info("Step 1 complete: database and user provisioned.")


# ---------------------------------------------------------------------------
# Step 2 — Grant full schema privileges (runs inside a transaction)
# ---------------------------------------------------------------------------

def grant_schema_privileges(cfg: dict[str, str]) -> None:
    """Grant full privileges on the public schema of the auth database.

    This step connects directly to the auth database and executes all GRANT
    statements inside a single transaction.  If any statement fails the
    entire transaction is rolled back, leaving no partial grants.

    Statements executed:
      * GRANT ALL ON SCHEMA public          — allows creating objects
      * GRANT ALL ON ALL TABLES             — existing tables
      * GRANT ALL ON ALL SEQUENCES          — existing sequences
      * ALTER DEFAULT PRIVILEGES … TABLES   — future tables
      * ALTER DEFAULT PRIVILEGES … SEQUENCES — future sequences

    Args:
        cfg: Config dict produced by :func:`load_config`.
    """
    logger.info(
        "Connecting to auth database '%s' to grant schema privileges.",
        cfg["auth_db_name"],
    )

    user = sql.Identifier(cfg["auth_db_user"])

    statements = [
        # Schema-level: allow creating tables, etc.
        sql.SQL("GRANT ALL PRIVILEGES ON SCHEMA public TO {user}").format(user=user),
        # Existing objects
        sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {user}").format(user=user),
        sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {user}").format(user=user),
        # Future objects (created by any role, not just the admin)
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {user}").format(user=user),
        sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {user}").format(user=user),
    ]

    # autocommit defaults to False → all statements run in one transaction.
    with psycopg.connect(
        host=cfg["admin_host"],
        port=int(cfg["admin_port"]),
        user=cfg["admin_user"],
        password=cfg["admin_password"],
        dbname=cfg["auth_db_name"],
        connect_timeout=5,
    ) as conn:
        try:
            with conn.cursor() as cur:
                for stmt in statements:
                    logger.info("Executing: %s", stmt.as_string(conn))
                    cur.execute(stmt)

            # Explicit commit — all grants succeed or none do.
            conn.commit()
            logger.info(
                "Step 2 complete: all privileges granted to '%s' on '%s'.",
                cfg["auth_db_user"],
                cfg["auth_db_name"],
            )

        except Exception:
            conn.rollback()
            logger.exception(
                "Failed to grant privileges — transaction rolled back. "
                "No privileges were changed."
            )
            raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Provision the auth database and user end-to-end."""
    cfg = load_config()

    logger.info(
        "Starting auth DB provisioning: db='%s', user='%s'.",
        cfg["auth_db_name"],
        cfg["auth_db_user"],
    )

    provision_database_and_user(cfg)
    grant_schema_privileges(cfg)

    logger.info("Auth DB provisioning finished successfully.")


if __name__ == "__main__":
    main()