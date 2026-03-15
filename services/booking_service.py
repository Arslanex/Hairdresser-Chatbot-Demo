"""Booking service for creating and managing appointments."""
from __future__ import annotations

from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Booking


class BookingService:
    """Handles all booking-related database operations.

    Provides methods to create, retrieve, and cancel appointment bookings.
    """

    async def create_booking(self, booking_data: dict, db: AsyncSession) -> Booking:
        """Create a new appointment booking in the database.

        Args:
            booking_data: Dictionary containing:
                - customer_name (str): Full name of the customer.
                - customer_phone (str): Customer's phone number.
                - service (str): Name of the service to book.
                - appointment_date (str): Date in YYYY-MM-DD format.
                - appointment_time (str): Time in HH:MM format.
                - whatsapp_id (str): WhatsApp sender ID.
                - staff_id (str): ID of the assigned staff member.
                - staff_name (str): Display name of the staff member.
                - location_type (str): "studio", "home", or "hotel".
                - branch_id (str): Branch identifier (for studio bookings).
                - visit_address (str | None): Visit address (for home/hotel).
                - total_price_tl (int | None): Total price in TL.
                - conversation_id (str): Conversation identifier.
            db: Async database session.

        Returns:
            Booking: The newly created booking record.
        """
        booking = Booking(
            customer_name=booking_data["customer_name"],
            customer_phone=booking_data["customer_phone"],
            service=booking_data["service"],
            appointment_date=booking_data["appointment_date"],
            appointment_time=booking_data["appointment_time"],
            status="confirmed",
            whatsapp_id=booking_data["whatsapp_id"],
            conversation_id=booking_data.get("conversation_id", ""),
            staff_id=booking_data.get("staff_id", ""),
            staff_name=booking_data.get("staff_name", ""),
            location_type=booking_data.get("location_type", "studio"),
            branch_id=booking_data.get("branch_id", ""),
            visit_address=booking_data.get("visit_address"),
            guest_count=booking_data.get("guest_count", 1),
            total_price_tl=booking_data.get("total_price_tl") or 0,
            created_at=_utcnow(),
        )
        db.add(booking)
        await db.flush()
        await db.refresh(booking)
        return booking

    async def get_bookings_by_phone(
        self, phone: str, db: AsyncSession
    ) -> list[Booking]:
        """Retrieve all bookings for a specific customer phone number.

        Args:
            phone: Customer phone number to search by.
            db: Async database session.

        Returns:
            List of Booking records for the given phone number.
        """
        result = await db.execute(
            select(Booking)
            .where(Booking.customer_phone == phone)
            .order_by(Booking.created_at.desc())
        )
        return list(result.scalars().all())

    async def cancel_booking(self, booking_id: int, db: AsyncSession) -> bool:
        """Cancel an existing booking by ID.

        Args:
            booking_id: Primary key of the booking to cancel.
            db: Async database session.

        Returns:
            True if the booking was found and cancelled, False otherwise.
        """
        result = await db.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()

        if booking is None:
            return False

        booking.status = "cancelled"
        await db.flush()
        return True
