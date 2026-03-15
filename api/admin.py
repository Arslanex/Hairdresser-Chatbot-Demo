"""Admin API routes for the hairdresser chatbot dashboard."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import AsyncSessionLocal
from database.models import AdminSetting, Booking, ConversationMessage, Session, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer(auto_error=False)

_TOKEN_EXPIRE_HOURS = 24

# ── Auth helpers ───────────────────────────────────────────────────────────────


def _create_token() -> str:
    payload = {
        "sub": "admin",
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.admin_secret_key, algorithm="HS256")


def _verify_token(token: str) -> bool:
    try:
        jwt.decode(token, settings.admin_secret_key, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    if credentials is None or not _verify_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── DB session dependency ──────────────────────────────────────────────────────


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()


# ── Pydantic schemas ───────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


class BookingOut(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    service: str
    appointment_date: str
    appointment_time: str
    staff_name: str
    location_type: str
    branch_id: str
    visit_address: str | None
    guest_count: int
    total_price_tl: int
    status: str
    whatsapp_id: str
    created_at: str


class ConversationOut(BaseModel):
    whatsapp_id: str
    customer_name: str | None
    last_message: str
    last_message_at: str
    message_count: int
    state: str
    takeover: bool


class MessageOut(BaseModel):
    id: int
    direction: str
    content: str
    message_type: str
    created_at: str


class SendMessageRequest(BaseModel):
    message: str


class TakeoverRequest(BaseModel):
    active: bool


class SettingOut(BaseModel):
    key: str
    value: str


class SettingIn(BaseModel):
    value: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/auth", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    """Authenticate with admin password and receive a JWT token."""
    if body.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong password")
    return LoginResponse(token=_create_token())


@router.get("/dashboard", dependencies=[Depends(require_admin)])
async def dashboard(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return summary stats for the admin dashboard."""
    today = datetime.now().strftime("%Y-%m-%d")

    today_count = await db.scalar(
        select(func.count(Booking.id)).where(
            Booking.appointment_date == today,
            Booking.status == "confirmed",
        )
    )
    total_confirmed = await db.scalar(
        select(func.count(Booking.id)).where(Booking.status == "confirmed")
    )
    total_cancelled = await db.scalar(
        select(func.count(Booking.id)).where(Booking.status == "cancelled")
    )
    active_sessions = await db.scalar(
        select(func.count(Session.id)).where(Session.state == "booking")
    )
    takeover_count = await db.scalar(
        select(func.count(Session.id)).where(Session.takeover == True)  # noqa: E712
    )
    total_users = await db.scalar(select(func.count(User.id)))

    # Last 5 confirmed bookings
    result = await db.execute(
        select(Booking)
        .where(Booking.status == "confirmed")
        .order_by(desc(Booking.created_at))
        .limit(5)
    )
    recent = result.scalars().all()

    return {
        "today_bookings": today_count or 0,
        "total_confirmed": total_confirmed or 0,
        "total_cancelled": total_cancelled or 0,
        "active_sessions": active_sessions or 0,
        "takeover_active": takeover_count or 0,
        "total_users": total_users or 0,
        "recent_bookings": [_booking_to_dict(b) for b in recent],
    }


@router.get("/appointments", dependencies=[Depends(require_admin)])
async def list_appointments(
    date: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    staff: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    whatsapp_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List appointments with optional filters."""
    q = select(Booking).order_by(
        desc(Booking.appointment_date), desc(Booking.appointment_time)
    )
    if date:
        q = q.where(Booking.appointment_date == date)
    if status_filter:
        q = q.where(Booking.status == status_filter)
    if staff:
        q = q.where(Booking.staff_id == staff)
    if branch:
        q = q.where(Booking.branch_id == branch)
    if whatsapp_id:
        q = q.where(Booking.whatsapp_id == whatsapp_id)

    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0

    result = await db.execute(q.limit(limit).offset(offset))
    bookings = result.scalars().all()

    return {
        "total": total,
        "items": [_booking_to_dict(b) for b in bookings],
    }


@router.patch("/appointments/{booking_id}", dependencies=[Depends(require_admin)])
async def update_appointment_status(
    booking_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a booking's status (e.g. confirmed → cancelled)."""
    new_status = body.get("status")
    if new_status not in ("confirmed", "cancelled"):
        raise HTTPException(status_code=400, detail="status must be 'confirmed' or 'cancelled'")
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    booking.status = new_status
    await db.flush()
    return _booking_to_dict(booking)


@router.get("/users/{whatsapp_id}", dependencies=[Depends(require_admin)])
async def get_user_profile(
    whatsapp_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return full profile for a user: info, session state, flow data, and bookings."""
    user_result = await db.execute(select(User).where(User.whatsapp_id == whatsapp_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session_result = await db.execute(select(Session).where(Session.whatsapp_id == whatsapp_id))
    session = session_result.scalar_one_or_none()

    bookings_result = await db.execute(
        select(Booking)
        .where(Booking.whatsapp_id == whatsapp_id)
        .order_by(desc(Booking.created_at))
    )
    bookings = bookings_result.scalars().all()

    msg_count = await db.scalar(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.whatsapp_id == whatsapp_id
        )
    ) or 0

    flow_data_parsed: dict = {}
    if session and session.flow_data:
        try:
            flow_data_parsed = json.loads(session.flow_data)
        except Exception:
            pass

    return {
        "whatsapp_id": user.whatsapp_id,
        "booking_phone": user.booking_phone,
        "created_at": user.created_at.isoformat(),
        "last_seen": user.last_seen.isoformat(),
        "message_count": msg_count,
        "session": {
            "state": session.state if session else "idle",
            "flow_step": session.flow_step if session else "",
            "flow_data": flow_data_parsed,
            "takeover": bool(session.takeover) if session else False,
            "last_activity": session.last_activity.isoformat() if session else None,
        },
        "bookings": [_booking_to_dict(b) for b in bookings],
    }


@router.post("/sessions/{whatsapp_id}/reset", dependencies=[Depends(require_admin)])
async def reset_session(
    whatsapp_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset a user's session to idle, clearing all flow state."""
    result = await db.execute(select(Session).where(Session.whatsapp_id == whatsapp_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.state = "idle"
    session.flow_step = ""
    session.flow_data = "{}"
    session.takeover = False
    await db.flush()
    return {"status": "reset", "whatsapp_id": whatsapp_id}


@router.get("/conversations", dependencies=[Depends(require_admin)])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all users with their last message and session state."""
    # Get all users with sessions
    result = await db.execute(
        select(User, Session)
        .outerjoin(Session, User.whatsapp_id == Session.whatsapp_id)
        .order_by(desc(User.last_seen))
    )
    rows = result.all()

    out = []
    for user, session in rows:
        # Get last message
        msg_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.whatsapp_id == user.whatsapp_id)
            .order_by(desc(ConversationMessage.created_at))
            .limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()

        count_result = await db.scalar(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.whatsapp_id == user.whatsapp_id
            )
        )

        # Get customer name from most recent booking
        name_result = await db.execute(
            select(Booking.customer_name)
            .where(Booking.whatsapp_id == user.whatsapp_id)
            .order_by(desc(Booking.created_at))
            .limit(1)
        )
        customer_name = name_result.scalar_one_or_none()

        out.append({
            "whatsapp_id": user.whatsapp_id,
            "customer_name": customer_name,
            "last_message": last_msg.content[:100] if last_msg else "",
            "last_message_at": last_msg.created_at.isoformat() if last_msg else user.last_seen.isoformat(),
            "message_count": count_result or 0,
            "state": session.state if session else "idle",
            "takeover": bool(session.takeover) if session else False,
        })
    return out


@router.get("/conversations/{whatsapp_id}", dependencies=[Depends(require_admin)])
async def get_conversation(
    whatsapp_id: str,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return message history for a specific user."""
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.whatsapp_id == whatsapp_id)
        .order_by(ConversationMessage.created_at)
        .limit(limit)
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "direction": m.direction,
            "content": m.content,
            "message_type": m.message_type,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


@router.post("/conversations/{whatsapp_id}/send", dependencies=[Depends(require_admin)])
async def send_manual_message(
    whatsapp_id: str,
    body: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a manual WhatsApp message from admin (takeover mode)."""
    wa_client = request.app.state.wa_client
    try:
        await wa_client.send_text(whatsapp_id, body.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WhatsApp send failed: {exc}") from exc

    # Persist as outgoing admin message
    db.add(ConversationMessage(
        whatsapp_id=whatsapp_id,
        direction="out",
        content=body.message,
        message_type="text",
    ))
    await db.flush()
    return {"status": "sent"}


@router.get("/takeover/{whatsapp_id}", dependencies=[Depends(require_admin)])
async def get_takeover(
    whatsapp_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current takeover status for a user."""
    result = await db.execute(
        select(Session).where(Session.whatsapp_id == whatsapp_id)
    )
    session = result.scalar_one_or_none()
    return {"whatsapp_id": whatsapp_id, "takeover": bool(session.takeover) if session else False}


@router.post("/takeover/{whatsapp_id}", dependencies=[Depends(require_admin)])
async def set_takeover(
    whatsapp_id: str,
    body: TakeoverRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enable or disable admin takeover for a specific user."""
    result = await db.execute(
        select(Session).where(Session.whatsapp_id == whatsapp_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.takeover = body.active
    await db.flush()
    return {"whatsapp_id": whatsapp_id, "takeover": body.active}


@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_settings(db: AsyncSession = Depends(get_db)) -> dict:
    """Return current settings (env defaults merged with DB overrides)."""
    defaults = {
        "business_name": settings.business_name,
        "business_phone": settings.business_phone,
        "business_address": settings.business_address,
        "working_hours_start": str(settings.working_hours_start),
        "working_hours_end": str(settings.working_hours_end),
        "working_days": json.dumps(settings.working_days),
        "bot_enabled": "true",
    }
    result = await db.execute(select(AdminSetting))
    db_overrides = {row.key: row.value for row in result.scalars().all()}
    return {**defaults, **db_overrides}


@router.put("/settings/{key}", dependencies=[Depends(require_admin)])
async def update_setting(
    key: str,
    body: SettingIn,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upsert a single admin setting value."""
    allowed_keys = {
        "business_name", "business_phone", "business_address",
        "working_hours_start", "working_hours_end", "working_days",
        "bot_enabled", "welcome_message",
    }
    if key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {key!r}")
    result = await db.execute(select(AdminSetting).where(AdminSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        db.add(AdminSetting(key=key, value=body.value))
    await db.flush()
    return {"key": key, "value": body.value}


# ── Prompt management ──────────────────────────────────────────────────────────

_PROMPT_KEYS = ("prompt_behavior", "prompt_business", "prompt_services", "prompt_staff")

_PROMPT_META = {
    "prompt_behavior": {
        "label": "Davranış & Ton",
        "description": "Botun genel kişiliği, dili ve hangi konularda yardımcı olacağı.",
    },
    "prompt_business": {
        "label": "İşletme Bilgileri",
        "description": "Salon adı, şubeler, adresler, telefon numaraları, çalışma saatleri.",
    },
    "prompt_services": {
        "label": "Hizmetler & Fiyatlar",
        "description": "Sunulan hizmetler, süreler, başlangıç fiyatları ve ek ücretler.",
    },
    "prompt_staff": {
        "label": "Sanatçılar & Ekip",
        "description": "Makeup artistlerin isimleri, unvanları, fiyatları ve uzmanlık alanları.",
    },
}


@router.get("/prompt", dependencies=[Depends(require_admin)])
async def get_prompt_sections(db: AsyncSession = Depends(get_db)) -> dict:
    """Return all 4 prompt sections with current values (DB or auto-generated defaults)."""
    from services.knowledge_service import get_default_prompt_sections
    defaults = get_default_prompt_sections()

    result = await db.execute(
        select(AdminSetting).where(AdminSetting.key.in_(list(_PROMPT_KEYS)))
    )
    db_vals = {row.key: row.value for row in result.scalars().all()}

    sections = []
    for key in _PROMPT_KEYS:
        meta = _PROMPT_META[key]
        value = db_vals.get(key) or defaults[key]
        sections.append({
            "key": key,
            "label": meta["label"],
            "description": meta["description"],
            "value": value,
            "is_default": key not in db_vals,
            "default_value": defaults[key],
        })

    # Assembled preview
    assembled = "\n\n".join(
        db_vals.get(k) or defaults[k] for k in _PROMPT_KEYS
    )
    return {"sections": sections, "assembled": assembled}


@router.put("/prompt/{key}", dependencies=[Depends(require_admin)])
async def update_prompt_section(
    key: str,
    body: SettingIn,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save a prompt section to DB (overrides the auto-generated default)."""
    if key not in _PROMPT_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown prompt key: {key!r}")
    result = await db.execute(select(AdminSetting).where(AdminSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = body.value
    else:
        db.add(AdminSetting(key=key, value=body.value))
    await db.flush()
    return {"key": key, "value": body.value}


@router.delete("/prompt/{key}", dependencies=[Depends(require_admin)])
async def reset_prompt_section(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset a prompt section to its auto-generated default by removing the DB override."""
    if key not in _PROMPT_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown prompt key: {key!r}")
    result = await db.execute(select(AdminSetting).where(AdminSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        await db.delete(setting)
        await db.flush()
    from services.knowledge_service import get_default_prompt_sections
    default_val = get_default_prompt_sections()[key]
    return {"key": key, "value": default_val, "is_default": True}


# ── SSE stream for live updates ────────────────────────────────────────────────

from fastapi.responses import StreamingResponse  # noqa: E402


@router.get("/stream", dependencies=[Depends(require_admin)])
async def live_stream(db: AsyncSession = Depends(get_db)):
    """Server-Sent Events endpoint for live dashboard updates."""
    async def event_generator():
        last_id = 0
        while True:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ConversationMessage)
                    .where(ConversationMessage.id > last_id)
                    .order_by(ConversationMessage.id)
                    .limit(20)
                )
                messages = result.scalars().all()
                for msg in messages:
                    last_id = msg.id
                    data = json.dumps({
                        "id": msg.id,
                        "whatsapp_id": msg.whatsapp_id,
                        "direction": msg.direction,
                        "content": msg.content[:200],
                        "created_at": msg.created_at.isoformat(),
                    }, ensure_ascii=False)
                    yield f"data: {data}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _booking_to_dict(b: Booking) -> dict:
    return {
        "id": b.id,
        "customer_name": b.customer_name,
        "customer_phone": b.customer_phone,
        "service": b.service,
        "appointment_date": b.appointment_date,
        "appointment_time": b.appointment_time,
        "staff_name": b.staff_name,
        "location_type": b.location_type,
        "branch_id": b.branch_id,
        "visit_address": b.visit_address,
        "guest_count": b.guest_count,
        "total_price_tl": b.total_price_tl,
        "status": b.status,
        "whatsapp_id": b.whatsapp_id,
        "created_at": b.created_at.isoformat(),
    }
