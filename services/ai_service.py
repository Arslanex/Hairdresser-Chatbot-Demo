"""Main AI orchestration service for routing and response generation."""
from __future__ import annotations

import json
import logging
import re
import time

import anthropic
from contextvars import ContextVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.context_guard import get_redirect_message, is_in_scope
from ai.intent_classifier import IntentClassifier
from config import settings

_USE_GROQ = getattr(settings, "use_groq_llm", False)
if _USE_GROQ:
    try:
        from groq import AsyncGroq
    except ImportError as e:
        raise ImportError(
            "Groq is required when USE_GROQ_LLM=1. Install with: pip install groq"
        ) from e
else:
    AsyncGroq = None  # type: ignore[misc, assignment]
from conversation_flows.booking_flow import BookingFlow, _surcharge
from conversation_flows.flow_engine import FlowEngine
from services.booking_service import BookingService
from services.user_service import UserService
from services.knowledge_service import BRANCHES, KnowledgeService, get_default_prompt_sections
from services.session_manager import SessionManager
from database.models import AdminSetting, Session as _SessionModel

logger = logging.getLogger(__name__)

# Flow steps driven by buttons/lists — no free-text intent classification needed
_STRUCTURED_FLOW_STEPS: frozenset[str] = frozenset(
    {"select_service", "select_location", "select_branch", "select_staff", "confirm", "get_guest_count",
     "select_time", "get_phone"}
)

# ── Back-navigation: intent → target step ─────────────────────────────────────
_INTENT_TO_STEP: dict[str, str] = {
    "provide_service":      "select_service",
    "provide_location":     "select_location",
    "provide_staff":        "select_staff",
    "provide_date":         "select_date",
    "provide_time":         "select_time",
    "provide_guest_count":  "get_guest_count",
    "provide_name":         "get_name",
    "provide_phone":        "get_phone",
}

# Step execution order (used to decide "is target earlier than current?")
_STEP_INDEX: dict[str, int] = {
    "select_service":    0,
    "select_location":   1,
    "select_branch":     2,
    "get_visit_address": 3,
    "select_staff":      4,
    "select_date":       5,
    "select_time":       6,
    "get_guest_count":   7,
    "get_name":          8,
    "get_phone":         9,
    "confirm":           10,
}

# flow_data keys to clear when jumping back to a step (downstream data becomes stale)
_STEP_CLEAR_KEYS: dict[str, list[str]] = {
    "select_service": [
        "service",
        "location_type", "location_label", "branch_id", "branch_name", "branch_address",
        "visit_address", "staff_id", "staff_name", "staff_title", "staff_price_tl",
        "appointment_date", "appointment_date_display", "appointment_time", "guest_count",
    ],
    "select_location": [
        "location_type", "location_label",
        "branch_id", "branch_name", "branch_address", "visit_address",
        "staff_id", "staff_name", "staff_title", "staff_price_tl",
        "appointment_date", "appointment_date_display", "appointment_time", "guest_count",
    ],
    "select_branch": [
        "branch_id", "branch_name", "branch_address",
        "staff_id", "staff_name", "staff_title", "staff_price_tl",
        "appointment_date", "appointment_date_display", "appointment_time", "guest_count",
    ],
    "select_staff":      ["appointment_date", "appointment_date_display", "appointment_time", "guest_count"],
    "select_date":       ["appointment_time", "guest_count"],
    "select_time":       ["guest_count"],
    "get_guest_count":   [],
    "get_name":          [],
    "get_phone":         [],
}

# User-facing confirmation shown before re-asking the step
_STEP_CHANGE_NOTICES: dict[str, str] = {
    "select_service":  "Tamam, hizmeti değiştirelim. 👇",
    "select_location": "Tamam, konumu değiştirelim. 👇",
    "select_branch":   "Tamam, şubeyi değiştirelim. 👇",
    "select_staff":    "Tamam, uzmanı değiştirelim. 👇",
    "select_date":     "Tamam, tarihi değiştirelim. 👇",
    "select_time":     "Tamam, saati değiştirelim. 👇",
    "get_guest_count": "Tamam, kişi sayısını değiştirelim. 👇",
    "get_name":        "Tamam, ismi düzeltelim. 👇",
    "get_phone":       "Tamam, telefonu düzeltelim. 👇",
}

# Per-request system prompt — set at the start of each process_message call.
# ContextVar ensures async-safety across concurrent requests.
_current_system_prompt: ContextVar[str] = ContextVar("system_prompt", default="")


class AIService:
    """Main AI orchestration service for the hairdresser chatbot."""

    def __init__(self) -> None:
        if _USE_GROQ:
            self._llm_client = AsyncGroq(api_key=settings.groq_api_key)
            self._use_groq = True
        else:
            self._llm_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=30.0,
            )
            self._use_groq = False
        self._intent_classifier = IntentClassifier()
        self._flow_engine = FlowEngine()
        self._knowledge_service = KnowledgeService()
        self._session_manager = SessionManager()
        self._booking_service = BookingService()
        self._user_service = UserService()
        self._booking_flow = BookingFlow()

    async def _load_system_prompt(self, db: AsyncSession) -> str:
        """Assemble system prompt from DB-stored sections (falls back to defaults)."""
        result = await db.execute(
            select(AdminSetting).where(
                AdminSetting.key.in_(
                    ["prompt_behavior", "prompt_business", "prompt_services", "prompt_staff"]
                )
            )
        )
        db_sections = {row.key: row.value for row in result.scalars().all()}
        defaults = get_default_prompt_sections()
        behavior = db_sections.get("prompt_behavior") or defaults["prompt_behavior"]
        business = db_sections.get("prompt_business") or defaults["prompt_business"]
        services = db_sections.get("prompt_services") or defaults["prompt_services"]
        staff    = db_sections.get("prompt_staff")    or defaults["prompt_staff"]
        return f"{behavior}\n\n{business}\n\n{services}\n\n{staff}"

    async def process_message(
        self, whatsapp_id: str, user_message: str, db: AsyncSession
    ) -> dict:
        """Process an incoming message and return a WhatsApp response payload."""
        # Load (and cache per-request) the assembled system prompt from DB
        system_prompt = await self._load_system_prompt(db)
        _current_system_prompt.set(system_prompt)

        await self._user_service.upsert_user(whatsapp_id, db)
        session = await self._session_manager.get_or_create_session(whatsapp_id, db)

        # ── Admin takeover: bot is paused for this user ────────────────────────────
        if getattr(session, "takeover", False):
            logger.info("[TAKEOVER] wa=%s — bot paused, skipping response", whatsapp_id)
            return {"type": "text", "text": ""}  # silent — admin is handling it

        flow_data: dict = json.loads(session.flow_data or "{}")
        history: list[dict] = flow_data.get("conversation_history", [])

        logger.info(
            "[TURN] wa=%s state=%-8s step=%-20s hist=%d msg=%r",
            whatsapp_id,
            session.state,
            session.flow_step or "-",
            len(history),
            user_message[:100],
        )

        # ── Active booking flow ────────────────────────────────────────────────────
        if session.state == "booking":
            # Stale confirm button: confirm_yes/confirm_no from an old WhatsApp message
            # arriving when the user is no longer at the confirm step.
            if (session.flow_step != "confirm"
                    and user_message.lower().strip() in {"confirm_yes", "confirm_no"}):
                logger.info(
                    "[BOOKING] wa=%s stale confirm button at step=%s — re-show current step",
                    whatsapp_id, session.flow_step,
                )
                flow_data_now = json.loads(session.flow_data or "{}")
                step_msg = self._booking_flow.get_current_step_message(session.flow_step, flow_data_now)
                return {"type": "multi", "messages": [
                    _text("Bu onay butonu artık geçerli değil. Devam edelim 👇"),
                    step_msg,
                ]}

            # Skip classification only for genuine button/list-reply IDs at structured steps.
            # Free-text inputs at structured steps are still classified (back-navigation support).
            is_button = session.flow_step in _STRUCTURED_FLOW_STEPS and _is_button_id(session.flow_step, user_message)
            if is_button:
                intent = {"intent": "", "confidence": 0.0, "entities": {}}
                logger.debug(
                    "[CLASSIFY] SKIP — structured button id at step=%s", session.flow_step
                )
            else:
                intent = await self._intent_classifier.classify_intent(
                    user_message, history, current_step=session.flow_step or ""
                )
            response = await self._handle_booking_flow(whatsapp_id, user_message, intent, db)
            # Persist conversation turn so intent classifier has booking context next time.
            # Skipped automatically if the session was reset (cancelled / finalized).
            await self._append_booking_history(whatsapp_id, user_message, response, db)
        else:
            intent = await self._intent_classifier.classify_intent(user_message, history)
            # Add user turn before generating response (gives Claude context)
            history.append({"role": "user", "content": user_message})
            flow_data["conversation_history"] = history[-10:]
            response = await self._route_by_intent(
                whatsapp_id, user_message, intent, flow_data, db
            )
            # Re-read the session: _route_by_intent may have transitioned to "booking"
            # (e.g. start_booking_flow was called). Only persist idle state if still idle.
            _res = await db.execute(select(_SessionModel).where(_SessionModel.whatsapp_id == whatsapp_id))
            _current = _res.scalar_one_or_none()
            if _current is None or _current.state == "idle":
                # Add assistant reply to history and persist both turns to DB
                assistant_text = _extract_response_text(response)
                if assistant_text:
                    flow_data["conversation_history"].append(
                        {"role": "assistant", "content": assistant_text}
                    )
                    flow_data["conversation_history"] = flow_data["conversation_history"][-10:]
                await self._session_manager.update_session(
                    whatsapp_id=whatsapp_id,
                    state="idle",
                    flow_step="",
                    flow_data=flow_data,
                    db=db,
                )
            else:
                logger.debug(
                    "[STATE-GUARD] wa=%s post-route state=%s → idle persist skipped",
                    whatsapp_id, _current.state if _current else "none",
                )

        return response

    # ─── Idle routing ─────────────────────────────────────────────────────────

    async def _route_by_intent(
        self,
        whatsapp_id: str,
        user_message: str,
        intent: dict,
        flow_data: dict,
        db: AsyncSession,
    ) -> dict:
        intent_name = intent.get("intent", "unknown")
        confidence = intent.get("confidence", 0.0)

        history: list[dict] = flow_data.get("conversation_history", [])

        # API failure or very low confidence → generic helpful response
        if intent_name == "unknown" or confidence < 0.25:
            logger.info(
                "[ROUTE] wa=%s intent=%s conf=%.2f → generic_response (low confidence)",
                whatsapp_id, intent_name, confidence,
            )
            return await self._generate_generic_response(user_message, history)

        # Out of scope / chitchat → polite redirect
        if not is_in_scope(intent_name):
            logger.info(
                "[ROUTE] wa=%s intent=%s conf=%.2f → out_of_scope redirect",
                whatsapp_id, intent_name, confidence,
            )
            return {"type": "text", "text": {"body": get_redirect_message()}}

        if intent_name == "greeting":
            logger.info("[ROUTE] wa=%s intent=greeting conf=%.2f → greeting_response", whatsapp_id, confidence)
            return await self._generate_greeting_response(user_message, history)

        if intent_name == "farewell":
            logger.info("[ROUTE] wa=%s intent=farewell conf=%.2f → farewell_response", whatsapp_id, confidence)
            return await self._generate_farewell_response(user_message, history)

        if intent_name == "booking_request":
            logger.info("[ROUTE] wa=%s intent=booking_request conf=%.2f → START booking flow", whatsapp_id, confidence)
            wa_phone = _format_wa_phone(whatsapp_id)
            return await self._flow_engine.start_booking_flow(
                whatsapp_id, db, whatsapp_phone=wa_phone
            )

        if intent_name in ("info_services", "info_price"):
            logger.info("[ROUTE] wa=%s intent=%s conf=%.2f → service_info", whatsapp_id, intent_name, confidence)
            return await self._handle_service_info(user_message, history)

        if intent_name == "info_hours":
            logger.info("[ROUTE] wa=%s intent=info_hours conf=%.2f → hours_info", whatsapp_id, confidence)
            return await self._handle_hours_info(user_message, history)

        if intent_name == "info_address":
            logger.info("[ROUTE] wa=%s intent=info_address conf=%.2f → address_info", whatsapp_id, confidence)
            return await self._handle_address_info(user_message, history)

        if intent_name == "cancel_booking":
            logger.info("[ROUTE] wa=%s intent=cancel_booking conf=%.2f → cancel info (idle)", whatsapp_id, confidence)
            return _text(
                "Randevunuzu iptal etmek için bize doğrudan ulaşabilirsiniz:\n\n"
                f"📞 {settings.business_phone}\n"
                f"📍 {settings.business_address}\n\n"
                "Başka bir konuda yardımcı olabilir miyim? 😊"
            )

        # affirmative/negative in idle state
        if intent_name in ("affirmative", "negative"):
            logger.info("[ROUTE] wa=%s intent=%s conf=%.2f → idle clarification", whatsapp_id, intent_name, confidence)
            return _text(
                "Randevu almak, hizmetlerimiz veya salon bilgileri hakkında "
                "size yardımcı olmaktan memnuniyet duyarım. Ne öğrenmek istersiniz? 😊"
            )

        # provide_* intents in idle state → start booking flow
        if intent_name.startswith("provide_"):
            logger.info(
                "[ROUTE] wa=%s intent=%s conf=%.2f → START booking flow (provide in idle)",
                whatsapp_id, intent_name, confidence,
            )
            wa_phone = _format_wa_phone(whatsapp_id)
            return await self._flow_engine.start_booking_flow(
                whatsapp_id, db, whatsapp_phone=wa_phone
            )

        logger.info("[ROUTE] wa=%s intent=%s conf=%.2f → generic_response (unmatched)", whatsapp_id, intent_name, confidence)
        return await self._generate_generic_response(user_message, history)

    async def _append_booking_history(
        self, whatsapp_id: str, user_message: str, response: dict, db: AsyncSession
    ) -> None:
        """Append one user+assistant turn to flow_data history during an active booking.

        Silently returns if the session is no longer in 'booking' state (i.e. it was
        cancelled or finalised inside _handle_booking_flow), so we never write to a
        stale or reset session.
        """
        session = await self._session_manager.get_or_create_session(whatsapp_id, db)
        if session.state != "booking":
            return

        flow_data = json.loads(session.flow_data or "{}")
        hist: list[dict] = flow_data.get("conversation_history", [])
        hist.append({"role": "user", "content": user_message})
        assistant_text = _extract_response_text(response)
        if assistant_text:
            hist.append({"role": "assistant", "content": assistant_text})
        flow_data["conversation_history"] = hist[-10:]
        await self._session_manager.update_session(
            whatsapp_id=whatsapp_id,
            state=session.state,
            flow_step=session.flow_step,
            flow_data=flow_data,
            db=db,
        )

    # ─── Booking flow ─────────────────────────────────────────────────────────

    async def _handle_booking_flow(
        self,
        whatsapp_id: str,
        user_message: str,
        intent: dict,
        db: AsyncSession,
    ) -> dict:
        session = await self._session_manager.get_or_create_session(whatsapp_id, db)
        current_step = session.flow_step
        intent_name = intent.get("intent", "")
        intent_conf = intent.get("confidence", 0.0)

        logger.debug(
            "[BOOKING] wa=%s step=%-20s intent=%-20s conf=%.2f",
            whatsapp_id, current_step, intent_name or "(button)", intent_conf,
        )

        # ── Another request already claimed finalization ───────────────────────
        if current_step == "finalizing":
            logger.warning("[BOOKING] wa=%s step=finalizing — duplicate request ignored", whatsapp_id)
            return _text("Randevunuz işleniyor, lütfen bekleyin... 🔄")

        # ── Already at "done" – atomically claim, then finalize ───────────────
        if current_step == "done":
            if not await self._session_manager.claim_finalization(whatsapp_id, db):
                logger.info("[BOOKING] wa=%s step=done — finalization already claimed", whatsapp_id)
                return _text("Randevunuz işleniyor, lütfen bekleyin... 🔄")
            logger.info("[BOOKING] wa=%s step=done → FINALIZE (claim won)", whatsapp_id)
            flow_data = json.loads(session.flow_data or "{}")
            return await self._finalize_booking(whatsapp_id, flow_data, session.conversation_id, db)

        # ── Restart: sıfırla ve hemen yeni flow başlat ────────────────────────
        if intent_name == "restart_booking":
            logger.info("[BOOKING] wa=%s RESTART at step=%s", whatsapp_id, current_step)
            await self._session_manager.reset_session(whatsapp_id, db)
            wa_phone = _format_wa_phone(whatsapp_id)
            return await self._flow_engine.start_booking_flow(
                whatsapp_id, db, whatsapp_phone=wa_phone
            )

        # ── Explicit cancellation (intent only, no keyword guessing) ──────────
        if intent_name in ("cancel_booking", "farewell") and current_step != "confirm":
            logger.info(
                "[BOOKING] wa=%s CANCEL at step=%s (intent=%s conf=%.2f)",
                whatsapp_id, current_step, intent_name, intent_conf,
            )
            await self._session_manager.reset_session(whatsapp_id, db)
            return _text(
                "Randevu alma işlemi iptal edildi. 😊\n\n"
                "İstediğiniz zaman tekrar randevu alabilirsiniz. "
                "Başka bir konuda yardımcı olabilir miyim?"
            )

        # ── Back-navigation: user wants to change a previously completed step ─
        # At confirm step, bare date/time/count inputs are likely accidental —
        # require an explicit change keyword before triggering back-nav.
        _CHANGE_KEYWORDS = {"değiştir", "yanlış", "değiş", "farklı", "düzelt", "başka", "olmadı", "olmaz"}
        if (current_step == "confirm"
                and intent_name in ("provide_date", "provide_time", "provide_guest_count")
                and not any(kw in user_message.lower() for kw in _CHANGE_KEYWORDS)):
            flow_data = json.loads(session.flow_data or "{}")
            step_msg = self._booking_flow.get_current_step_message("confirm", flow_data)
            return {"type": "multi", "messages": [
                _text("Onaylamak için *Evet* butonuna, iptal için *Hayır* butonuna basın."),
                step_msg,
            ]}

        target_step = _resolve_back_step(intent_name, current_step)
        if target_step:
            logger.info(
                "[BOOKING] wa=%s BACK-NAV intent=%s current=%s → %s (clearing: %s)",
                whatsapp_id, intent_name, current_step, target_step,
                _STEP_CLEAR_KEYS.get(target_step, []),
            )
            flow_data = json.loads(session.flow_data or "{}")
            for key in _STEP_CLEAR_KEYS.get(target_step, []):
                flow_data.pop(key, None)
            await self._session_manager.update_session(
                whatsapp_id=whatsapp_id,
                state="booking",
                flow_step=target_step,
                flow_data=flow_data,
                db=db,
            )
            notice = _STEP_CHANGE_NOTICES.get(target_step, "Tamam, değiştirelim. 👇")
            step_msg = self._booking_flow.get_current_step_message(target_step, flow_data)
            return {"type": "multi", "messages": [_text(notice), step_msg]}

        # ── Off-topic intents mid-flow: answer briefly, then re-show current step ─
        if intent_name == "greeting":
            logger.info("[BOOKING] wa=%s GREETING mid-flow at step=%s → re-show step", whatsapp_id, current_step)
            flow_data = json.loads(session.flow_data or "{}")
            step_msg = self._booking_flow.get_current_step_message(current_step, flow_data)
            return {"type": "multi", "messages": [
                _text("Merhaba! 😊 Randevunuza devam edelim."),
                step_msg,
            ]}

        if intent_name in ("info_services", "info_price", "info_hours", "info_address", "chitchat"):
            logger.info("[BOOKING] wa=%s intent=%s mid-flow at step=%s → answer + re-show", whatsapp_id, intent_name, current_step)
            flow_data = json.loads(session.flow_data or "{}")
            history: list[dict] = flow_data.get("conversation_history", [])
            if intent_name in ("info_services", "info_price"):
                info_response = await self._handle_service_info(user_message, history)
            elif intent_name == "info_hours":
                info_response = await self._handle_hours_info(user_message, history)
            elif intent_name == "info_address":
                info_response = await self._handle_address_info(user_message, history)
            else:
                info_response = await self._generate_generic_response(user_message, history)
            step_msg = self._booking_flow.get_current_step_message(current_step, flow_data)
            info_text = _extract_response_text(info_response)
            return {"type": "multi", "messages": [
                _text(info_text),
                _text("Randevunuza devam edelim 👇"),
                step_msg,
            ]}

        result = await self._flow_engine.process_flow_input(
            whatsapp_id, user_message, intent, db
        )

        # ── Check if flow just completed ──────────────────────────────────────
        session = await self._session_manager.get_or_create_session(whatsapp_id, db)
        if session.flow_step == "done":
            if not await self._session_manager.claim_finalization(whatsapp_id, db):
                logger.info("[BOOKING] wa=%s step=done — finalization already claimed (post-flow)", whatsapp_id)
                return _text("Randevunuz işleniyor, lütfen bekleyin... 🔄")
            logger.info("[BOOKING] wa=%s step=done → FINALIZE (post-flow claim won)", whatsapp_id)
            flow_data = json.loads(session.flow_data or "{}")
            return await self._finalize_booking(whatsapp_id, flow_data, session.conversation_id, db)

        return result

    async def _finalize_booking(
        self, whatsapp_id: str, flow_data: dict, conversation_id: str, db: AsyncSession
    ) -> dict:
        confirmed = flow_data.get("confirmed", False)

        logger.info(
            "[FINALIZE] wa=%s conv_id=%.8s confirmed=%s service=%r staff=%r "
            "date=%s time=%s location=%s price=%sTL guest=%d",
            whatsapp_id,
            conversation_id,
            confirmed,
            flow_data.get("service", "?"),
            flow_data.get("staff_name", "?"),
            flow_data.get("appointment_date", "?"),
            flow_data.get("appointment_time", "?"),
            flow_data.get("location_type", "?"),
            flow_data.get("staff_price_tl", "?"),
            flow_data.get("guest_count", 1),
        )

        if not confirmed:
            logger.info("[FINALIZE] wa=%s → user declined → session reset", whatsapp_id)
            await self._session_manager.reset_session(whatsapp_id, db)
            return _text(
                "Randevu iptal edildi. 😊\n\n"
                "Tekrar randevu almak isterseniz her zaman buradayım!"
            )

        # ── Step 1: create booking — retryable on failure ─────────────────────
        try:
            # Use the same surcharge function as the confirm screen so DB price matches UI
            total_price = flow_data.get("staff_price_tl", 0) + _surcharge(flow_data)

            booking = await self._booking_service.create_booking(
                {
                    "customer_name":    flow_data.get("customer_name", ""),
                    "customer_phone":   flow_data.get("customer_phone", ""),
                    "service":          flow_data.get("service", ""),
                    "appointment_date": flow_data.get("appointment_date", ""),
                    "appointment_time": flow_data.get("appointment_time", ""),
                    "whatsapp_id":      whatsapp_id,
                    "staff_id":         flow_data.get("staff_id", ""),
                    "staff_name":       flow_data.get("staff_name", ""),
                    "location_type":    flow_data.get("location_type", "studio"),
                    "branch_id":        flow_data.get("branch_id", ""),
                    "visit_address":    flow_data.get("visit_address", ""),
                    "guest_count":      flow_data.get("guest_count", 1),
                    "total_price_tl":   total_price,
                    "conversation_id":  conversation_id,
                },
                db,
            )
        except Exception as exc:
            logger.error("[FINALIZE] wa=%s booking creation FAILED: %s", whatsapp_id, exc)
            # Roll back to confirm so the user can retry (Evet) or cancel (Hayır)
            await self._session_manager.update_session(
                whatsapp_id=whatsapp_id,
                state="booking",
                flow_step="confirm",
                flow_data=flow_data,
                db=db,
            )
            return _text(
                "Üzgünüz, randevunuz kaydedilirken teknik bir sorun oluştu. 😔\n\n"
                "Tekrar denemek için *Evet*, iptal etmek için *Hayır* yazabilirsiniz."
            )

        # ── Step 2: booking created — reset session regardless of what follows ─
        # Errors here must NOT roll back to confirm; the booking already exists.
        logger.info(
            "[FINALIZE] wa=%s booking_id=%d CREATED — customer=%r phone=%r",
            whatsapp_id, booking.id,
            flow_data.get("customer_name", "?"),
            flow_data.get("customer_phone", "?"),
        )
        await self._session_manager.reset_session(whatsapp_id, db)
        try:
            await self._user_service.save_booking_phone(
                whatsapp_id, flow_data.get("customer_phone", ""), db
            )
        except Exception as exc:
            logger.warning("[FINALIZE] wa=%s save_booking_phone failed: %s", whatsapp_id, exc)

        date_display = flow_data.get("appointment_date_display", flow_data.get("appointment_date", ""))
        return _text(
            f"✅ Randevunuz başarıyla oluşturuldu!\n\n"
            f"🆔 Randevu No: #{booking.id}\n"
            f"💄 Hizmet: {booking.service}\n"
            f"👤 Uzman: {booking.staff_name}\n"
            f"👥 Kişi: {flow_data.get('guest_count', 1)}\n"
            f"📅 Tarih: {date_display}\n"
            f"🕐 Saat: {booking.appointment_time}\n"
            f"💰 Ücret: {f'{booking.total_price_tl:,}'.replace(',', '.')} TL\n\n"
            f"Bizi tercih ettiğiniz için teşekkür ederiz! "
            f"Herhangi bir sorunuz olursa {settings.business_phone} numarasını arayabilirsiniz. 😊"
        )

    # ─── Info handlers ────────────────────────────────────────────────────────

    async def _generate_greeting_response(
        self, user_message: str, history: list[dict]
    ) -> dict:
        branch = list(BRANCHES.values())[0]
        hours = self._knowledge_service.get_working_hours()
        text = await self._call_claude(
            user_message=user_message,
            context=(
                f"Kullanıcı salonu selamlıyor. Sıcak ve samimi bir karşılama yap.\n\n"
                f"Salon: {settings.business_name}\n"
                f"Telefon: {settings.business_phone} / {branch['phone_2']}\n"
                f"Adres: {branch['address']}\n"
                f"Çalışma saatleri: {hours}\n"
                "Sunulan hizmetler: Düğün/Kına/Nişan Saç & Makyaj, Türban Tasarım, "
                "Profesyonel Saç & Makyaj, Tırnak İşlemleri, Saç Bakım Hizmetleri.\n\n"
                "3-4 cümle. Salonu tanıt, randevu alma veya hizmet/fiyat sorularında "
                "yardımcı olabileceğini belirt."
            ),
            history=history,
        )
        return _text(text)

    async def _generate_farewell_response(
        self, user_message: str, history: list[dict]
    ) -> dict:
        text = await self._call_claude(
            user_message=user_message,
            context=(
                "Kullanıcı veda ediyor. Sıcak ve samimi bir veda mesajı yaz. "
                "Kısa tut (1-2 cümle). Tekrar beklendiğini belirt."
            ),
            history=history,
        )
        return _text(text)

    async def _handle_service_info(
        self, user_message: str, history: list[dict]
    ) -> dict:
        business_info = self._knowledge_service.get_business_info()
        text = await self._call_claude(
            user_message=user_message,
            context=f"Salon bilgileri:\n{business_info}\n\nBu bilgileri kullanarak soruyu yanıtla.",
            history=history,
        )
        return _text(text)

    async def _handle_hours_info(
        self, user_message: str, history: list[dict]
    ) -> dict:
        hours = self._knowledge_service.get_working_hours()
        text = await self._call_claude(
            user_message=user_message,
            context=f"Çalışma saatleri: {hours}\nBu bilgiyi kullanarak soruyu yanıtla.",
            history=history,
        )
        return _text(text)

    async def _handle_address_info(
        self, user_message: str, history: list[dict]
    ) -> dict:
        branch = list(BRANCHES.values())[0]
        text = await self._call_claude(
            user_message=user_message,
            context=(
                f"Adres: {branch['name']}, {branch['address']}\n"
                f"Telefon: {settings.business_phone}\n"
                "Bu bilgileri kullanarak soruyu yanıtla."
            ),
            history=history,
        )
        return _text(text)

    async def _generate_generic_response(
        self, user_message: str, history: list[dict]
    ) -> dict:
        business_info = self._knowledge_service.get_business_info()
        text = await self._call_claude(
            user_message=user_message,
            context=(
                f"Salon bilgileri:\n{business_info}\n\n"
                "Kullanıcının mesajına bu bilgileri kullanarak yardımcı ol. "
                "Konu salon dışındaysa kibarca salon konularına yönlendir."
            ),
            history=history,
        )
        return _text(text)

    # ─── Claude call ──────────────────────────────────────────────────────────

    async def _call_claude(
        self,
        user_message: str,
        context: str,
        history: list[dict] | None = None,
    ) -> str:
        base_prompt = _current_system_prompt.get() or "\n\n".join(
            get_default_prompt_sections().values()
        )
        system = f"{base_prompt}\n\nEk bağlam:\n{context}" if context else base_prompt
        # Build messages from conversation history so Claude retains context.
        # history[-8:] includes the current user turn at the end; use it directly.
        messages: list[dict] = []
        if history:
            for entry in history[-8:]:
                if entry.get("role") in ("user", "assistant") and entry.get("content"):
                    messages.append({"role": entry["role"], "content": entry["content"]})
        if not messages or messages[-1].get("role") != "user":
            messages.append({"role": "user", "content": user_message})

        model_id = settings.groq_model if self._use_groq else settings.claude_response_model
        logger.debug("[LLM] model=%s hist_turns=%d ctx_chars=%d", model_id, len(messages), len(system))

        t0 = time.monotonic()
        try:
            if self._use_groq:
                groq_messages = [{"role": "system", "content": system}]
                groq_messages.extend(messages)
                response = await self._llm_client.chat.completions.create(
                    model=settings.groq_model,
                    max_completion_tokens=1024,
                    messages=groq_messages,
                )
                text = (response.choices[0].message.content or "Size nasıl yardımcı olabilirim? 😊").strip()
            else:
                response = await self._llm_client.messages.create(
                    model=settings.claude_response_model,
                    max_tokens=1024,
                    thinking={"type": "adaptive"},
                    system=system,
                    messages=messages,
                )
                text = "Size nasıl yardımcı olabilirim? 😊"
                for block in response.content:
                    if block.type == "text":
                        text = block.text.strip()
                        break

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.info("[LLM] model=%s elapsed=%dms reply=%r", model_id, elapsed_ms, text[:80])
            return text

        except anthropic.APIError as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error("[LLM] Claude API error after %dms: %s", elapsed_ms, exc)
            return (
                "Şu an teknik bir sorun yaşıyoruz. "
                f"Lütfen {settings.business_phone} numarasını arayın veya biraz sonra tekrar deneyin."
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if self._use_groq:
                logger.error("[LLM] Groq API error after %dms: %s", elapsed_ms, exc)
                return (
                    "Şu an teknik bir sorun yaşıyoruz. "
                    f"Lütfen {settings.business_phone} numarasını arayın veya biraz sonra tekrar deneyin."
                )
            raise


def _is_button_id(step: str, text: str) -> bool:
    """Return True only when *text* is a structured button/list-reply ID for *step*.

    Anything that looks like free text (e.g. 'hizmetimi değiştir') returns False
    so the intent classifier runs and back-navigation can kick in.
    """
    lower = text.lower().strip()
    if step == "select_service":
        return bool(re.fullmatch(r"svc_\d+", lower))
    if step == "select_location":
        return lower in {"studio", "hotel", "out_of_city", "stüdyo", "stüdyoya", "otel", "otele"}
    if step == "select_branch":
        return lower in {"gaziantep", "istanbul"}
    if step == "select_staff":
        return bool(re.fullmatch(r"staff_\w+", lower))
    if step == "confirm":
        return lower in {"confirm_yes", "confirm_no"}
    if step == "get_guest_count":
        return bool(re.fullmatch(r"\d{1,2}", lower))
    if step == "select_time":
        return bool(re.fullmatch(r"time_\d{4}", lower))
    if step == "get_phone":
        return lower in {"phone_use_wa", "phone_enter_new"}
    return False


def _resolve_back_step(intent_name: str, current_step: str) -> str | None:
    """Return the step to jump back to, or None if no back-navigation applies.

    Only triggers when the target step is strictly earlier than the current step,
    so the same intent at its own step (e.g. provide_service at select_service)
    passes through to the normal flow processor.
    """
    # At get_visit_address the user is typing an address that naturally contains
    # "otel" / "hotel" — don't let that word trigger back-navigation to select_location.
    if current_step == "get_visit_address" and intent_name == "provide_location":
        return None

    target = _INTENT_TO_STEP.get(intent_name)
    if not target:
        return None
    if _STEP_INDEX.get(target, 999) < _STEP_INDEX.get(current_step, 0):
        return target
    return None


def _text(body: str) -> dict:
    return {"type": "text", "text": {"body": body}}


def _extract_response_text(response: dict) -> str:
    """Extract a plain-text summary from any response payload type."""
    if response.get("type") == "text":
        text_val = response.get("text", {})
        return text_val.get("body", "") if isinstance(text_val, dict) else (text_val or "")
    if response.get("type") == "multi":
        parts = [
            m.get("text", {}).get("body", "")
            for m in response.get("messages", [])
            if m.get("type") == "text"
        ]
        return " ".join(filter(None, parts))
    # interactive messages: store a generic placeholder so history has a turn
    if response.get("type") == "interactive":
        return response.get("interactive", {}).get("body", {}).get("text", "")
    return ""


def _format_wa_phone(whatsapp_id: str) -> str:
    """Format a raw WhatsApp ID for display (e.g. '905321234567' → '+90 532 123 45 67')."""
    digits = re.sub(r"\D", "", whatsapp_id)
    if len(digits) == 12 and digits.startswith("90"):
        n = digits[2:]
        return f"+90 {n[:3]} {n[3:6]} {n[6:8]} {n[8:]}"
    if len(digits) == 11 and digits.startswith("0"):
        n = digits[1:]
        return f"0{n[:3]} {n[3:6]} {n[6:8]} {n[8:]}"
    return f"+{digits}" if not whatsapp_id.startswith("+") else whatsapp_id
