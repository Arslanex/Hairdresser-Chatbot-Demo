"""WhatsApp webhook message extraction and processing."""
from __future__ import annotations

import json
import logging
import time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ConversationMessage, ProcessedMessage
from integrations.whatsapp.client import WhatsAppClient
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Processes incoming WhatsApp webhook payloads.

    Extracts message data from the raw webhook body, delegates to the AI
    service for response generation, and sends the result via WhatsApp.
    """

    def extract_message(self, webhook_data: dict) -> dict | None:
        """Extract relevant message fields from a WhatsApp webhook payload.

        Handles both regular text messages and interactive reply messages
        (button_reply, list_reply).

        Args:
            webhook_data: Raw JSON payload received from the WhatsApp webhook.

        Returns:
            Dict with 'phone', 'message_id', 'text', and 'type' keys,
            or None if no processable message is found.
        """
        try:
            entry = webhook_data.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            phone = msg.get("from", "")
            message_id = msg.get("id", "")
            msg_type = msg.get("type", "")

            text = ""

            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                interactive_type = interactive.get("type", "")

                if interactive_type == "button_reply":
                    button_reply = interactive.get("button_reply", {})
                    # Use the id so flow engine can match it
                    text = button_reply.get("id", "") or button_reply.get("title", "")
                elif interactive_type == "list_reply":
                    list_reply = interactive.get("list_reply", {})
                    text = list_reply.get("id", "") or list_reply.get("title", "")

            if not phone:
                return None

            # Empty or whitespace-only: no processable content
            if not text or not text.strip():
                if msg_type == "reaction":
                    # Emoji reactions are silent — no response needed
                    return None
                return {
                    "phone": phone,
                    "message_id": message_id,
                    "type": msg_type or "text",
                    "empty": True,
                }

            return {
                "phone": phone,
                "message_id": message_id,
                "text": text,
                "type": msg_type,
            }

        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Failed to extract message from webhook: %s", exc)
            return None

    async def process_webhook(
        self,
        webhook_data: dict,
        db: AsyncSession,
        ai_service: AIService,
        wa_client: WhatsAppClient,
    ) -> None:
        """Process an incoming WhatsApp webhook event end-to-end.

        Extracts the message, generates a response via AI service, and sends
        the response back through the WhatsApp client. Handles multi-message
        responses (type='multi') transparently.

        Args:
            webhook_data: Raw JSON payload from the WhatsApp webhook POST.
            db: Async database session.
            ai_service: AI orchestration service instance.
            wa_client: WhatsApp API client instance.
        """
        extracted = self.extract_message(webhook_data)
        if extracted is None:
            logger.debug("No processable message in webhook payload")
            return

        phone = extracted["phone"]
        message_id = extracted.get("message_id", "")

        # ── Idempotency: skip already-processed messages ───────────────────────
        if message_id:
            try:
                db.add(ProcessedMessage(message_id=message_id))
                await db.flush()
            except IntegrityError:
                await db.rollback()
                logger.info("Duplicate message_id %r from %s — skipping", message_id, phone)
                return

        # Empty or whitespace-only message
        if extracted.get("empty"):
            logger.debug("Empty message from %s — sending hint", phone)
            try:
                await wa_client.send_text(
                    phone,
                    "Mesajınız boş görünüyor. Randevu almak, hizmetler veya çalışma saatleri "
                    "hakkında yazabilirsiniz. 😊",
                )
            except Exception as exc:
                logger.error("Failed to send empty-message reply to %s: %s", phone, exc)
            return

        # Non-text message types (image, audio, video, document, sticker, …)
        if extracted.get("unsupported"):
            logger.info(
                "Unsupported message type %r from %s — sending canned reply",
                extracted.get("type"),
                phone,
            )
            try:
                await wa_client.send_text(
                    phone,
                    "Üzgünüm, yalnızca yazılı mesajları anlayabiliyorum. "
                    "Lütfen mesajınızı yazı ile iletir misiniz? 🙏",
                )
            except Exception as exc:
                logger.error("Failed to send unsupported-type reply to %s: %s", phone, exc)
            return

        text = extracted["text"]
        msg_type = extracted.get("type", "text")
        logger.info(
            "[MSG] wa=%s id=%s type=%s text=%r",
            phone, message_id[-8:] if len(message_id) > 8 else message_id,
            msg_type, text[:100],
        )

        # Persist incoming message for admin UI
        db.add(ConversationMessage(
            whatsapp_id=phone,
            direction="in",
            content=text,
            message_type=msg_type,
        ))

        t0 = time.monotonic()
        try:
            response_message = await ai_service.process_message(
                whatsapp_id=phone,
                user_message=text,
                db=db,
            )

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            resp_type = response_message.get("type", "?")
            if resp_type == "multi":
                n = len(response_message.get("messages", []))
                logger.info("[SENT] wa=%s type=multi(%d) elapsed=%dms", phone, n, elapsed_ms)
            else:
                logger.info("[SENT] wa=%s type=%s elapsed=%dms", phone, resp_type, elapsed_ms)

            # Takeover mode: empty text means bot is silent
            text_field = response_message.get("text", "")
            text_body = text_field.get("body", "") if isinstance(text_field, dict) else text_field
            if response_message.get("type") == "text" and not text_body.strip():
                return

            # Persist outgoing message(s) for admin UI
            _save_outgoing_messages(db, phone, response_message)

            await self._send_response(wa_client, phone, response_message)

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "[ERROR] wa=%s elapsed=%dms err=%s", phone, elapsed_ms, exc, exc_info=True
            )
            # Send a generic error message to the user
            try:
                await wa_client.send_text(
                    phone,
                    "Teknik bir sorun oluştu. Lütfen biraz sonra tekrar deneyin. 🙏",
                )
            except Exception as send_exc:
                logger.error("Failed to send error message to %s: %s", phone, send_exc)

    async def _send_response(
        self,
        wa_client: WhatsAppClient,
        phone: str,
        message: dict,
    ) -> None:
        """Send a response message, handling multi-message payloads.

        Args:
            wa_client: WhatsApp API client instance.
            phone: Recipient phone number.
            message: WhatsApp message payload dict. If type is 'multi',
                each sub-message in 'messages' list is sent sequentially.
        """
        if message.get("type") == "multi":
            for sub_message in message.get("messages", []):
                await wa_client.send_message(phone, sub_message)
        else:
            await wa_client.send_message(phone, message)


def _save_outgoing_messages(db: AsyncSession, phone: str, message: dict) -> None:
    """Persist outgoing bot message(s) to conversation_messages for admin UI."""
    if message.get("type") == "multi":
        for sub in message.get("messages", []):
            content = _extract_text_content(sub)
            db.add(ConversationMessage(
                whatsapp_id=phone,
                direction="out",
                content=content,
                message_type=sub.get("type", "text"),
            ))
    else:
        content = _extract_text_content(message)
        db.add(ConversationMessage(
            whatsapp_id=phone,
            direction="out",
            content=content,
            message_type=message.get("type", "text"),
        ))


def _extract_text_content(message: dict) -> str:
    """Extract a human-readable text representation from a message dict."""
    msg_type = message.get("type", "text")
    if msg_type == "text":
        text_field = message.get("text", "")
        if isinstance(text_field, dict):
            return text_field.get("body", "")
        return text_field if isinstance(text_field, str) else ""
    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        header = interactive.get("header", {}).get("text", "")
        body = interactive.get("body", {}).get("text", "")
        return f"{header}\n{body}".strip() if header else body
    # Fallback: JSON summary
    return json.dumps(message, ensure_ascii=False)[:500]
