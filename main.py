"""Main FastAPI application entry point for the hairdresser chatbot."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.admin import router as admin_router
from api.webhook import router as webhook_router
from config import settings
from database.connection import AsyncSessionLocal, init_db
from integrations.whatsapp.client import WhatsAppClient
from integrations.whatsapp.message_processor import MessageProcessor
from services.ai_service import AIService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    On startup: initializes the database and instantiates service singletons.
    On shutdown: logs a clean shutdown message.

    Args:
        app: The FastAPI application instance.
    """
    use_groq = getattr(settings, "use_groq_llm", False)
    llm_backend = (
        f"Groq [{settings.groq_model}]"
        if use_groq
        else f"Claude [classifier={settings.claude_classifier_model} / response={settings.claude_response_model}]"
    )
    logger.info("Starting %s chatbot — LLM: %s", settings.business_name, llm_backend)

    # Initialize database tables
    await init_db()
    logger.info("Database initialized — url=%s", settings.database_url)

    # Instantiate services and attach to app state
    app.state.ai_service = AIService()
    app.state.wa_client = WhatsAppClient()
    app.state.message_processor = MessageProcessor()

    logger.info(
        "Services initialized — business=%r phone=%s working_days=%s hours=%02d:00-%02d:00",
        settings.business_name,
        settings.business_phone,
        settings.working_days,
        settings.working_hours_start,
        settings.working_hours_end,
    )
    logger.info("Application ready")

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title=f"{settings.business_name} Chatbot",
    description=(
        "WhatsApp-based hairdresser appointment chatbot powered by Claude claude-opus-4-6. "
        "Handles bookings, service inquiries, and salon information in Turkish."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(admin_router)

# Serve built React admin UI (only when dist exists)
import os  # noqa: E402
_admin_dist = os.path.join(os.path.dirname(__file__), "admin-ui", "dist")
if os.path.isdir(_admin_dist):
    app.mount("/admin-ui", StaticFiles(directory=_admin_dist, html=True), name="admin-ui")


@app.get("/", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint.

    Verifies database connectivity in addition to basic service status.

    Returns:
        JSON dict with status, service name, version, and db check result.
    """
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check DB ping failed: %s", exc)
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": f"{settings.business_name} Chatbot",
        "version": "1.0.0",
        "db": db_status,
    }
