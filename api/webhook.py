"""Webhook API routes for WhatsApp message reception and verification."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from config import settings
from database.connection import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Verify the X-Hub-Signature-256 header against the request body.

    If WHATSAPP_APP_SECRET is not configured the check is skipped (returns True),
    so the app works during local development without requiring the secret.
    """
    app_secret = settings.whatsapp_app_secret
    if not app_secret:
        return True  # secret not configured — skip verification
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
) -> int:
    """Verify the WhatsApp webhook during initial setup.

    WhatsApp sends a GET request with hub.mode='subscribe', a hub.challenge
    token, and the hub.verify_token. We must echo back hub.challenge on success.

    Args:
        hub_mode: Should be 'subscribe' for verification.
        hub_challenge: Random challenge string to echo back.
        hub_verify_token: Token we set when registering the webhook.

    Returns:
        The hub.challenge value as an integer on successful verification.

    Raises:
        HTTPException: 403 if the verify token does not match.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("Webhook verified successfully")
        return int(hub_challenge)

    logger.warning(
        "Webhook verification failed: mode=%r, token=%r", hub_mode, hub_verify_token
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed",
    )


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(request: Request) -> dict:
    """Receive incoming WhatsApp messages and process them asynchronously.

    Returns 200 OK to WhatsApp immediately (required within 20 seconds),
    then processes the message in a background task with its own DB session.

    Args:
        request: The incoming FastAPI request containing the webhook payload.

    Returns:
        Simple status dict confirming receipt.
    """
    # Read raw body once — needed for both signature verification and JSON parsing
    try:
        body = await request.body()
    except Exception as exc:
        logger.warning("Failed to read webhook body: %s", exc)
        return {"status": "ok"}

    # Verify HMAC-SHA256 signature (skipped if WHATSAPP_APP_SECRET is not set)
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    try:
        webhook_data: dict = json.loads(body)
    except Exception as exc:
        logger.warning("Failed to parse webhook JSON: %s", exc)
        return {"status": "ok"}

    ai_service = request.app.state.ai_service
    wa_client = request.app.state.wa_client
    message_processor = request.app.state.message_processor

    async def _process_in_background() -> None:
        async with AsyncSessionLocal() as db:
            try:
                await message_processor.process_webhook(
                    webhook_data=webhook_data,
                    db=db,
                    ai_service=ai_service,
                    wa_client=wa_client,
                )
                await db.commit()
            except Exception as exc:
                logger.error("Webhook processing error: %s", exc, exc_info=True)
                await db.rollback()

    task = asyncio.create_task(_process_in_background())

    def _on_task_done(t: asyncio.Task) -> None:
        if not t.cancelled() and (exc := t.exception()):
            logger.error("Background webhook task raised unhandled exception: %s", exc)

    task.add_done_callback(_on_task_done)
    return {"status": "ok"}
