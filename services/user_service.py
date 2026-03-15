"""User service for managing WhatsApp user profiles."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserService:
    """Manages user records keyed by WhatsApp ID."""

    async def upsert_user(self, whatsapp_id: str, db: AsyncSession) -> User:
        """Create or update a user record on every incoming message."""
        result = await db.execute(
            select(User).where(User.whatsapp_id == whatsapp_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(whatsapp_id=whatsapp_id)
            db.add(user)
        user.last_seen = _utcnow()
        await db.flush()
        return user

    async def save_booking_phone(
        self, whatsapp_id: str, phone: str, db: AsyncSession
    ) -> None:
        """Persist the contact phone from a completed booking."""
        result = await db.execute(
            select(User).where(User.whatsapp_id == whatsapp_id)
        )
        user = result.scalar_one_or_none()
        if user is not None and phone:
            user.booking_phone = phone
            user.last_seen = _utcnow()
            await db.flush()
