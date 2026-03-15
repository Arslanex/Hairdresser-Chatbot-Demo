"""Flow engine orchestrating the booking conversation flow."""
from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from conversation_flows.booking_flow import BookingFlow
from services.session_manager import SessionManager

logger = logging.getLogger(__name__)

_booking_flow = BookingFlow()
_session_manager = SessionManager()

_VALIDATION_HINTS: dict[str, str] = {
    "select_service":    "Geçersiz seçim. Lütfen listeden bir hizmet seçin.",
    "select_location":   "Stüdyo, Otel veya Şehir Dışı Otel seçeneklerinden birini seçin.",
    "get_visit_address": (
        "Lütfen geçerli bir adres girin (en az 10 karakter).\n"
        "Örnek: Atatürk Mah. Gül Sk. No:12 D:3, Kadıköy / İstanbul"
    ),
    "select_staff":      "Geçersiz seçim. Lütfen listeden bir uzman seçin.",
    "select_date": (
        "Geçersiz tarih. Lütfen gelecekteki bir çalışma günü girin.\n"
        "Örnekler: yarın, haftaya cuma, 15/04/2026"
    ),
    "select_time": (
        "Geçersiz saat. Lütfen mevcut saatlerden birini seçin ya da şöyle yazın:\n"
        "öğleden sonra 3, sabah 10, 14:30, akşam 6"
    ),
    "get_guest_count": "Lütfen geçerli bir sayı girin (1-20 arası).",
    "get_name":    "Lütfen *ad ve soyadınızı* birlikte girin.\nÖrnek: Ayşe Yılmaz",
    "get_phone":   "Geçersiz telefon numarası. Lütfen Türk mobil formatında girin.\nÖrnek: 0532 123 45 67",
    "confirm":     "Lütfen 'Evet' veya 'Hayır' şeklinde yanıtlayın.",
}


class FlowEngine:
    """Orchestrates the multi-step booking flow lifecycle."""

    async def start_booking_flow(
        self, whatsapp_id: str, db: AsyncSession, whatsapp_phone: str = ""
    ) -> dict:
        """Initialize a new booking session, preserving conversation history."""
        session = await _session_manager.get_or_create_session(whatsapp_id, db)
        existing_data = json.loads(session.flow_data or "{}")
        initial_flow_data = {
            "conversation_history": existing_data.get("conversation_history", []),
            "whatsapp_phone": whatsapp_phone,
        }
        await _session_manager.update_session(
            whatsapp_id=whatsapp_id,
            state="booking",
            flow_step="select_service",
            flow_data=initial_flow_data,
            db=db,
        )
        logger.info("[FLOW] wa=%s START → step=select_service (prev_state=%s)", whatsapp_id, session.state)
        return _booking_flow.get_current_step_message("select_service", initial_flow_data)

    async def process_flow_input(
        self,
        whatsapp_id: str,
        user_message: str,
        intent: dict,
        db: AsyncSession,
    ) -> dict:
        """Process user input, advance the flow, and return the next message."""
        session = await _session_manager.get_or_create_session(whatsapp_id, db)
        current_step = session.flow_step
        flow_data: dict = json.loads(session.flow_data or "{}")

        is_valid, next_step, updated_data = _booking_flow.process_step_input(
            step=current_step,
            user_input=user_message,
            intent=intent,
            flow_data=flow_data,
        )

        if not is_valid:
            logger.info(
                "[FLOW] wa=%s step=%-20s input=%r → INVALID → re-ask",
                whatsapp_id, current_step, user_message[:60],
            )
            # Still touch last_activity so timeout is measured from the latest
            # message, not from the last successful step.
            await _session_manager.update_session(
                whatsapp_id=whatsapp_id,
                state="booking",
                flow_step=current_step,
                flow_data=flow_data,
                db=db,
            )
            return self._invalid_input_response(current_step, flow_data)

        # Log accepted values (the interesting keys that changed)
        _changed = {k: updated_data[k] for k in updated_data if updated_data.get(k) != flow_data.get(k) and k != "conversation_history"}
        logger.info(
            "[FLOW] wa=%s step=%-20s input=%r → VALID → next=%-20s accepted=%s",
            whatsapp_id, current_step, user_message[:60], next_step,
            {k: v for k, v in _changed.items() if v} if _changed else "{}",
        )

        # Persist new state
        await _session_manager.update_session(
            whatsapp_id=whatsapp_id,
            state="booking",
            flow_step=next_step,
            flow_data=updated_data,
            db=db,
        )
        return _booking_flow.get_current_step_message(next_step, updated_data)

    async def is_in_flow(self, whatsapp_id: str, db: AsyncSession) -> bool:
        session = await _session_manager.get_or_create_session(whatsapp_id, db)
        return session.state == "booking"

    # ─── private ─────────────────────────────────────────────────────────────

    def _invalid_input_response(self, step: str, flow_data: dict) -> dict:
        """Build a helpful error + re-ask message for a failed validation step."""
        hint = _VALIDATION_HINTS.get(step, "")
        step_msg = _booking_flow.get_current_step_message(step, flow_data)

        if not hint:
            return step_msg

        step_type = step_msg.get("type", "text")

        if step_type == "text":
            # Prepend hint directly into the text body
            original = step_msg["text"]["body"]
            step_msg["text"]["body"] = f"⚠️ {hint}\n\n{original}"
            return step_msg

        # For interactive messages return a multi-message so the hint
        # is sent as text first, then the interactive payload follows
        return {
            "type": "multi",
            "messages": [
                {"type": "text", "text": {"body": f"⚠️ {hint}"}},
                step_msg,
            ],
        }
