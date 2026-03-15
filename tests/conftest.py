"""Global test fixtures.

Environment variables must be set *before* config.py is imported anywhere.

- Default: ANTHROPIC_API_KEY=test-key-not-real (config loads; no real LLM calls).
- To use Groq in tests (faster/cheaper): set in .env:
    USE_GROQ_LLM=1
    GROQ_API_KEY=gsk_...   # from https://console.groq.com/
  Then run: pytest
"""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("USE_GROQ_LLM", "0")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test-phone-id")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify")
os.environ.setdefault("WHATSAPP_APP_SECRET", "")
