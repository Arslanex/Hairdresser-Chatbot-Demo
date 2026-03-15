"""SQLAlchemy ORM models for the hairdresser chatbot."""
from __future__ import annotations

from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class User(Base):
    """Represents a WhatsApp user profile.

    Attributes:
        id: Primary key, auto-incremented.
        whatsapp_id: Unique WhatsApp sender ID (phone number).
        booking_phone: Contact phone saved from a completed booking.
        created_at: Timestamp of first contact.
        last_seen: Timestamp of most recent message.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whatsapp_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    booking_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), default=_utcnow
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, whatsapp_id={self.whatsapp_id!r})"


class Booking(Base):
    """Represents a hair salon appointment booking.

    Attributes:
        id: Primary key, auto-incremented.
        customer_name: Full name of the customer.
        customer_phone: Customer's phone number.
        service: Name of the booked service.
        appointment_date: Date of appointment in YYYY-MM-DD format.
        appointment_time: Time of appointment in HH:MM format.
        status: Booking status (confirmed, cancelled).
        whatsapp_id: WhatsApp sender ID who created the booking.
        created_at: Timestamp when the booking was created.
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False)
    appointment_date: Mapped[str] = mapped_column(String(10), nullable=False)
    appointment_time: Mapped[str] = mapped_column(String(5), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    staff_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    location_type: Mapped[str] = mapped_column(String(20), nullable=False, default="studio")
    branch_id: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    visit_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_price_tl: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="confirmed")
    whatsapp_id: Mapped[str] = mapped_column(String(100), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"Booking(id={self.id!r}, customer_name={self.customer_name!r}, "
            f"service={self.service!r}, date={self.appointment_date!r}, "
            f"time={self.appointment_time!r}, status={self.status!r})"
        )


class Session(Base):
    """Represents a WhatsApp conversation session with state machine.

    Attributes:
        id: Primary key, auto-incremented.
        whatsapp_id: Unique WhatsApp sender ID.
        state: Current state of the conversation (idle, booking).
        flow_step: Current step within the active flow.
        flow_data: JSON-serialized dict containing flow context data.
        last_activity: Timestamp of the last message in this session.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whatsapp_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="idle")
    flow_step: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    flow_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_activity: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
    )
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    conversation_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    takeover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"Session(id={self.id!r}, whatsapp_id={self.whatsapp_id!r}, "
            f"state={self.state!r}, flow_step={self.flow_step!r})"
        )


class ConversationMessage(Base):
    """Stores individual messages exchanged with each user.

    Attributes:
        id: Primary key, auto-incremented.
        whatsapp_id: WhatsApp sender ID.
        direction: 'in' for user messages, 'out' for bot/admin replies.
        content: Text content of the message.
        message_type: Original WhatsApp message type (text, interactive, …).
        created_at: Timestamp when the message was stored.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    whatsapp_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "in" | "out"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"ConversationMessage(id={self.id!r}, whatsapp_id={self.whatsapp_id!r}, "
            f"direction={self.direction!r})"
        )


class AdminSetting(Base):
    """Persists admin-editable settings as key-value pairs.

    Attributes:
        key: Setting key (primary key).
        value: Setting value (stored as string/JSON).
        updated_at: Timestamp of last update.
    """

    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return f"AdminSetting(key={self.key!r}, value={self.value!r})"


class ProcessedMessage(Base):
    """Tracks processed WhatsApp message IDs to prevent duplicate handling.

    Attributes:
        message_id: Unique WhatsApp message ID (primary key).
        processed_at: Timestamp when the message was first processed.
    """

    __tablename__ = "processed_messages"

    message_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return f"ProcessedMessage(message_id={self.message_id!r})"
