"""Async SQLAlchemy database connection and session management."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables and applying lightweight migrations.

    This function should be called once at application startup.
    """
    from database.models import AdminSetting, Booking, ConversationMessage, ProcessedMessage, Session, User  # noqa: F401

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_apply_migrations)
        logger.info("Database tables initialized successfully.")
    except Exception:
        logger.exception("Failed to initialize database tables.")
        raise


def _apply_migrations(conn) -> None:  # type: ignore[no-untyped-def]
    """Add any missing columns to existing tables (idempotent ALTER TABLE migrations)."""
    from sqlalchemy import inspect, text

    inspector = inspect(conn)

    # bookings table — columns added after initial schema
    _ensure_columns(conn, inspector, "bookings", [
        ("staff_id",        "VARCHAR(100)  NOT NULL DEFAULT ''"),
        ("staff_name",      "VARCHAR(255)  NOT NULL DEFAULT ''"),
        ("location_type",   "VARCHAR(20)   NOT NULL DEFAULT 'studio'"),
        ("branch_id",       "VARCHAR(50)   NOT NULL DEFAULT ''"),
        ("visit_address",   "TEXT"),
        ("guest_count",     "INTEGER       NOT NULL DEFAULT 1"),
        ("total_price_tl",  "INTEGER       NOT NULL DEFAULT 0"),
        ("conversation_id", "VARCHAR(50)   NOT NULL DEFAULT ''"),
    ])

    # sessions table — columns added after initial schema
    _ensure_columns(conn, inspector, "sessions", [
        ("conversation_id",         "VARCHAR(36)  NOT NULL DEFAULT ''"),
        ("conversation_started_at", "DATETIME"),
        ("takeover",                "INTEGER      NOT NULL DEFAULT 0"),
    ])


def _ensure_columns(conn, inspector, table: str, columns: list[tuple[str, str]]) -> None:  # type: ignore[no-untyped-def]
    """Add *columns* to *table* if they don't already exist."""
    from sqlalchemy import text

    existing = {col["name"] for col in inspector.get_columns(table)}
    for col_name, col_def in columns:
        if col_name not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
            logger.info("Migration: added column '%s' to table '%s'", col_name, table)
