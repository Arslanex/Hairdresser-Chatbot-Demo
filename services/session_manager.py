"""Session manager for conversation state persistence."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime (SQLite-compatible)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Session
from config import settings


class SessionManager:
    """Manages WhatsApp conversation sessions stored in the database.

    Each session tracks the current conversation state, active flow step,
    and any accumulated flow data for multi-step interactions.
    """

    async def get_or_create_session(
        self, whatsapp_id: str, db: AsyncSession
    ) -> Session:
        """Retrieve an existing session or create a new one.

        If the last activity is older than conversation_timeout_hours, the
        session is reset to idle (any pending booking is discarded) and a new
        conversation_id is assigned.
        """
        result = await db.execute(
            select(Session).where(Session.whatsapp_id == whatsapp_id)
        )
        session = result.scalar_one_or_none()
        now = _utcnow()

        if session is None:
            session = Session(
                whatsapp_id=whatsapp_id,
                state="idle",
                flow_step="",
                flow_data="{}",
                conversation_id=str(uuid.uuid4()),
                conversation_started_at=now,
                last_activity=now,
            )
            db.add(session)
            await db.flush()
            return session

        # Unstick sessions left in "finalizing" for more than 5 minutes.
        # This happens when the process crashes between claim_finalization and
        # reset_session; without this the user would see "işleniyor" forever.
        _FINALIZING_TIMEOUT = timedelta(minutes=5)
        if (
            session.flow_step == "finalizing"
            and (now - session.last_activity) > _FINALIZING_TIMEOUT
        ):
            session.state = "idle"
            session.flow_step = ""
            session.flow_data = "{}"
            session.conversation_id = str(uuid.uuid4())
            session.conversation_started_at = now
            await db.flush()
            return session

        # Expire conversation after inactivity
        timeout = timedelta(hours=settings.conversation_timeout_hours)
        if (now - session.last_activity) > timeout:
            session.state = "idle"
            session.flow_step = ""
            session.flow_data = "{}"
            session.conversation_id = str(uuid.uuid4())
            session.conversation_started_at = now
            await db.flush()

        return session

    async def update_session(
        self,
        whatsapp_id: str,
        state: str,
        flow_step: str,
        flow_data: dict,
        db: AsyncSession,
    ) -> None:
        """Update an existing session with new state and flow information.

        Args:
            whatsapp_id: The WhatsApp sender identifier.
            state: New conversation state (idle, booking).
            flow_step: Current step name within the active flow.
            flow_data: Dictionary of accumulated flow context data.
            db: Async database session.
        """
        result = await db.execute(
            select(Session).where(Session.whatsapp_id == whatsapp_id)
        )
        session = result.scalar_one_or_none()

        if session is None:
            session = Session(
                whatsapp_id=whatsapp_id,
                conversation_id=str(uuid.uuid4()),
                conversation_started_at=_utcnow(),
            )
            db.add(session)

        session.state = state
        session.flow_step = flow_step
        session.flow_data = json.dumps(flow_data, ensure_ascii=False)
        session.last_activity = _utcnow()
        await db.flush()

    async def reset_session(self, whatsapp_id: str, db: AsyncSession) -> None:
        """Reset a session to idle, preserving conversation_history across bookings."""
        result = await db.execute(
            select(Session).where(Session.whatsapp_id == whatsapp_id)
        )
        session = result.scalar_one_or_none()

        if session is not None:
            existing = json.loads(session.flow_data or "{}")
            preserved = {
                "conversation_history": existing.get("conversation_history", [])
            }
            session.state = "idle"
            session.flow_step = ""
            session.flow_data = json.dumps(preserved, ensure_ascii=False)
            session.last_activity = _utcnow()
            await db.flush()

    async def claim_finalization(self, whatsapp_id: str, db: AsyncSession) -> bool:
        """Atomically transition flow_step from 'done' to 'finalizing'.

        Only one concurrent request can win this transition; all others receive
        False and should return a "processing" message to the user.

        Returns:
            True  — this request won the race and should call _finalize_booking.
            False — another request already claimed finalization; do nothing.
        """
        result = await db.execute(
            sa_update(Session)
            .where(Session.whatsapp_id == whatsapp_id, Session.flow_step == "done")
            .values(flow_step="finalizing")
            .execution_options(synchronize_session="fetch")
        )
        await db.flush()
        return result.rowcount == 1

    async def get_conversation_id(
        self, whatsapp_id: str, db: AsyncSession
    ) -> str:
        """Return the current conversation_id for a user."""
        result = await db.execute(
            select(Session).where(Session.whatsapp_id == whatsapp_id)
        )
        session = result.scalar_one_or_none()
        return session.conversation_id if session else ""
