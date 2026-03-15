"""WhatsApp Cloud API client for sending messages."""
from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Async HTTP client for the WhatsApp Cloud API.

    Reads token and phone_number_id from settings at construction time so that
    tests can override settings before instantiation without hitting module-load
    ordering issues.

    Provides high-level methods for sending text, interactive button, and
    interactive list messages via the WhatsApp Business API.
    """

    def __init__(self) -> None:
        self._base_url = (
            f"https://graph.facebook.com/v18.0"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        self._headers = {
            "Authorization": f"Bearer {settings.whatsapp_token}",
            "Content-Type": "application/json",
        }

    async def send_message(self, phone_number: str, message: dict) -> dict:
        """Send a pre-formatted WhatsApp message payload to a recipient.

        Args:
            phone_number: Recipient's phone number (E.164 format, e.g. "905321234567").
            message: WhatsApp message dict (type + content fields).

        Returns:
            API response JSON as a dict.
        """
        payload: dict = {
            "messaging_product": "whatsapp",
            "to": phone_number,
        }

        msg_type = message.get("type", "text")
        payload["type"] = msg_type

        if msg_type == "text":
            payload["text"] = message.get("text", {})
        elif msg_type == "interactive":
            payload["interactive"] = message.get("interactive", {})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._base_url, json=payload, headers=self._headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.RequestError as exc:
            logger.error("WhatsApp API request error: %s", exc)
            raise

    async def send_text(self, phone_number: str, text: str) -> dict:
        """Send a plain text message.

        Args:
            phone_number: Recipient's phone number in E.164 format.
            text: Message body text.

        Returns:
            API response JSON as a dict.
        """
        return await self.send_message(
            phone_number,
            {"type": "text", "text": {"body": text}},
        )

    async def send_interactive_buttons(
        self,
        phone_number: str,
        body: str,
        buttons: list[dict],
    ) -> dict:
        """Send an interactive message with reply buttons.

        Args:
            phone_number: Recipient's phone number in E.164 format.
            body: Main message body text.
            buttons: List of button dicts, each with 'type', 'reply.id', and
                'reply.title' keys. Maximum 3 buttons.

        Returns:
            API response JSON as a dict.
        """
        return await self.send_message(
            phone_number,
            {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body},
                    "action": {"buttons": buttons},
                },
            },
        )

    async def send_interactive_list(
        self,
        phone_number: str,
        header: str,
        body: str,
        sections: list[dict],
    ) -> dict:
        """Send an interactive message with a scrollable list.

        Args:
            phone_number: Recipient's phone number in E.164 format.
            header: Header text displayed above the body.
            body: Main message body text.
            sections: List of section dicts with 'title' and 'rows' keys.
                Each row has 'id', 'title', and optional 'description'.

        Returns:
            API response JSON as a dict.
        """
        return await self.send_message(
            phone_number,
            {
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "header": {"type": "text", "text": header},
                    "body": {"text": body},
                    "action": {
                        "button": "Seç",
                        "sections": sections,
                    },
                },
            },
        )
