"""Application configuration using pydantic-settings."""
from __future__ import annotations

import json

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file.

    Attributes:
        anthropic_api_key: API key for Anthropic Claude (required when not using Groq).
        use_groq_llm: If True, use Groq Cloud API for intent + response (e.g. in tests).
        groq_api_key: API key for Groq (required when use_groq_llm=True).
        groq_model: Groq model ID for both classifier and response (e.g. llama-3.3-70b-versatile).
        whatsapp_token: WhatsApp Cloud API bearer token.
        whatsapp_phone_number_id: WhatsApp phone number ID for sending messages.
        whatsapp_verify_token: Token for webhook verification.
        database_url: SQLAlchemy async database URL.
        business_name: Display name of the salon.
        business_phone: Contact phone number of the salon.
        business_address: Physical address of the salon.
        claude_response_model: Claude model used for response generation.
        claude_classifier_model: Claude model used for intent classification.
        working_hours_start: Opening hour (24h format).
        working_hours_end: Closing hour (24h format).
        working_days: List of working days (0=Monday, 6=Sunday).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    anthropic_api_key: str = ""
    use_groq_llm: bool = False
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    claude_response_model: str = "claude-opus-4-6"
    claude_classifier_model: str = "claude-haiku-4-5"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "webhook_verify_token"
    whatsapp_app_secret: str = ""   # Used for X-Hub-Signature-256 verification
    database_url: str = "sqlite+aiosqlite:///./hairdresser.db"
    business_name: str = "İzellik Makeup House"
    business_phone: str = "+90 549 272 0101"
    business_address: str = "Gaziantep"
    working_hours_start: int = 9
    working_hours_end: int = 19
    working_days: list[int] = [0, 1, 2, 3, 4, 5]
    conversation_timeout_hours: int = 4
    admin_password: str = "admin123"
    admin_secret_key: str = "hairdresser_admin_secret_change_me"

    @field_validator("working_days", mode="before")
    @classmethod
    def parse_working_days(cls, v: object) -> list[int]:
        """Accept both a Python list and a JSON string (e.g. '[0,1,2,3,4,5]')."""
        if isinstance(v, str):
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError("WORKING_DAYS must be a JSON array of integers")
            return [int(d) for d in parsed]
        return list(v)  # type: ignore[arg-type]

    @field_validator("use_groq_llm", mode="before")
    @classmethod
    def parse_use_groq_llm(cls, v: object) -> bool:
        """Accept 1/0, true/false, yes/no from env."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return bool(v)

    @model_validator(mode="after")
    def check_llm_config(self) -> "Settings":
        """Require either Anthropic key (production) or Groq key when use_groq_llm."""
        if self.use_groq_llm:
            if not self.groq_api_key or self.groq_api_key.startswith("your_") or self.groq_api_key == "test-key-not-real":
                raise ValueError(
                    "GROQ_API_KEY must be set to a valid key when USE_GROQ_LLM is enabled. "
                    "Get one at https://console.groq.com/"
                )
        else:
            if not self.anthropic_api_key or self.anthropic_api_key.startswith("your_"):
                raise ValueError(
                    "ANTHROPIC_API_KEY must be set when not using Groq. "
                    "Or set USE_GROQ_LLM=1 and GROQ_API_KEY for tests."
                )
        return self


settings = Settings()
