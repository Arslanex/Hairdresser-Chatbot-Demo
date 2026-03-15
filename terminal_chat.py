"""Terminal chat interface for testing the hairdresser chatbot locally."""
from __future__ import annotations

import asyncio
import json
import os
import sys

# Load .env before importing project modules
from dotenv import load_dotenv
load_dotenv()

from database.connection import AsyncSessionLocal, init_db
from services.ai_service import AIService

# ── ANSI colours ─────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
GREY   = "\033[90m"
RED    = "\033[91m"
BLUE   = "\033[94m"

USER_ID = "terminal_test_user"


def _render_response(payload: dict) -> str:
    """Convert a WhatsApp message payload to a readable terminal string."""
    msg_type = payload.get("type", "text")

    if msg_type == "text":
        return payload["text"]["body"]

    if msg_type == "interactive":
        interactive = payload["interactive"]
        itype = interactive.get("type")
        lines: list[str] = []

        # Header
        header = interactive.get("header", {})
        if header.get("text"):
            lines.append(f"{BOLD}{header['text']}{RESET}")

        # Body
        body_text = interactive.get("body", {}).get("text", "")
        if body_text:
            lines.append(body_text)

        # Choices
        if itype == "button":
            buttons = interactive.get("action", {}).get("buttons", [])
            lines.append("")
            lines.append(f"{YELLOW}Seçenekler:{RESET}")
            for i, btn in enumerate(buttons, 1):
                reply = btn.get("reply", {})
                lines.append(f"  {YELLOW}[{i}]{RESET} {reply.get('title', '')}  "
                              f"{GREY}(id: {reply.get('id', '')}){RESET}")

        elif itype == "list":
            sections = interactive.get("action", {}).get("sections", [])
            lines.append("")
            lines.append(f"{YELLOW}Liste:{RESET}")
            for section in sections:
                if section.get("title"):
                    lines.append(f"  {BOLD}{section['title']}{RESET}")
                for i, row in enumerate(section.get("rows", []), 1):
                    desc = f" — {row['description']}" if row.get("description") else ""
                    lines.append(f"  {YELLOW}[{i}]{RESET} {row['title']}{GREY}{desc}{RESET}  "
                                  f"{GREY}(id: {row['id']}){RESET}")

        # Footer
        footer = interactive.get("footer", {}).get("text", "")
        if footer:
            lines.append(f"\n{GREY}{footer}{RESET}")

        return "\n".join(lines)

    if msg_type == "multi":
        # Internal multi-message type (hint + interactive)
        parts = payload.get("messages", [])
        return "\n\n".join(_render_response(p) for p in parts)

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _resolve_interactive_input(raw: str, last_payload: dict | None) -> str:
    """
    If the last bot message had buttons/list and the user typed a number (1,2,3…)
    return the corresponding WhatsApp reply id, otherwise return raw input.
    """
    if last_payload is None:
        return raw

    stripped = raw.strip()

    # Only resolve numeric shortcuts
    try:
        choice = int(stripped)
    except ValueError:
        return raw

    msg_type = last_payload.get("type")

    # Unwrap multi-message — use the last part (interactive)
    if msg_type == "multi":
        messages = last_payload.get("messages", [])
        if messages:
            last_payload = messages[-1]
            msg_type = last_payload.get("type")

    if msg_type != "interactive":
        return raw

    interactive = last_payload.get("interactive", {})
    itype = interactive.get("type")

    if itype == "button":
        buttons = interactive.get("action", {}).get("buttons", [])
        if 1 <= choice <= len(buttons):
            return buttons[choice - 1]["reply"]["id"]

    elif itype == "list":
        rows: list[dict] = []
        for section in interactive.get("action", {}).get("sections", []):
            rows.extend(section.get("rows", []))
        if 1 <= choice <= len(rows):
            return rows[choice - 1]["id"]

    return raw


def _print_banner() -> None:
    print(f"\n{BOLD}{CYAN}{'═' * 54}{RESET}")
    print(f"{BOLD}{CYAN}   Kuaför Chatbot — Terminal Test{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 54}{RESET}")
    print(f"{GREY}  Çıkmak için: 'quit' veya 'exit' veya Ctrl-C{RESET}")
    print(f"{GREY}  Oturumu sıfırlamak için: '/reset'{RESET}")
    print(f"{CYAN}{'─' * 54}{RESET}\n")


async def main() -> None:
    _print_banner()

    # Initialise DB and service
    await init_db()
    ai_service = AIService()

    last_payload: dict | None = None

    while True:
        # ── User input ────────────────────────────────────────────
        try:
            raw = input(f"{GREEN}{BOLD}Sen:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GREY}Görüşürüz!{RESET}\n")
            break

        if not raw:
            continue

        if raw.lower() in ("quit", "exit", "q"):
            print(f"\n{GREY}Görüşürüz!{RESET}\n")
            break

        # Session reset helper
        if raw.lower() == "/reset":
            from services.session_manager import SessionManager
            async with AsyncSessionLocal() as db:
                await SessionManager().reset_session(USER_ID, db)
            last_payload = None
            print(f"{YELLOW}  ↺ Oturum sıfırlandı.{RESET}\n")
            continue

        # Resolve number shortcut → WhatsApp reply id
        resolved = _resolve_interactive_input(raw, last_payload)
        if resolved != raw:
            print(f"{GREY}  → seçim: {resolved}{RESET}")

        # ── Call AI service ───────────────────────────────────────
        print(f"{GREY}  …{RESET}", end="\r")
        try:
            async with AsyncSessionLocal() as db:
                payload = await ai_service.process_message(USER_ID, resolved, db)
        except Exception as exc:
            print(f"{RED}  Hata: {exc}{RESET}\n")
            continue

        last_payload = payload

        # ── Render response ───────────────────────────────────────
        rendered = _render_response(payload)
        print(f"\n{BLUE}{BOLD}Bot:{RESET}")
        for line in rendered.splitlines():
            print(f"  {line}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
