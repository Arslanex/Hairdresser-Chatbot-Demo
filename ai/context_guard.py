"""Context guard to prevent out-of-scope conversations."""
from __future__ import annotations

_OUT_OF_SCOPE_INTENTS: frozenset[str] = frozenset({"out_of_scope", "chitchat"})

_REDIRECT_MESSAGE = (
    "Üzgünüm, bu konuda yardımcı olamıyorum. Ben yalnızca salonumuzla ilgili "
    "konularda destek verebiliyorum. Randevu almak, hizmetlerimiz, çalışma saatlerimiz "
    "veya adresimiz hakkında sormak istediğiniz bir şey var mı?"
)


def is_in_scope(intent: str) -> bool:
    """Check whether the classified intent is within the chatbot's scope.

    Args:
        intent: The classified intent string.

    Returns:
        True if the intent is in scope (salon-related), False otherwise.
    """
    return intent not in _OUT_OF_SCOPE_INTENTS


def get_redirect_message() -> str:
    """Return a polite Turkish message redirecting users to salon topics.

    Returns:
        Redirect message string in Turkish.
    """
    return _REDIRECT_MESSAGE
