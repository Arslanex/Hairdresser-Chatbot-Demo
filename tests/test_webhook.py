"""Tests for webhook signature verification."""
import hashlib
import hmac
from unittest.mock import patch

from api.webhook import _verify_signature


class TestVerifySignature:
    def _make_sig(self, secret: str, body: bytes) -> str:
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_no_secret_skips_verification(self):
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = ""
            assert _verify_signature(b'{"any": "body"}', "") is True

    def test_valid_signature(self):
        body = b'{"object":"whatsapp_business_account"}'
        secret = "supersecret123"
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = secret
            assert _verify_signature(body, self._make_sig(secret, body)) is True

    def test_wrong_signature(self):
        body = b'{"object":"whatsapp_business_account"}'
        secret = "supersecret123"
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = secret
            assert _verify_signature(body, "sha256=wrongvalue") is False

    def test_tampered_body(self):
        body = b'{"object":"whatsapp_business_account"}'
        tampered = b'{"object":"TAMPERED"}'
        secret = "supersecret123"
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = secret
            sig = self._make_sig(secret, body)
            assert _verify_signature(tampered, sig) is False

    def test_missing_sha256_prefix(self):
        body = b"test"
        secret = "secret"
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = secret
            # Header without sha256= prefix
            assert _verify_signature(body, "invalidsig") is False

    def test_empty_header_with_secret_set(self):
        with patch("api.webhook.settings") as mock_settings:
            mock_settings.whatsapp_app_secret = "secret"
            assert _verify_signature(b"body", "") is False
