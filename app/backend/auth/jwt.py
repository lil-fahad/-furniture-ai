from datetime import datetime, timedelta
from typing import Any, Dict


class JWTAuth:
    """Lightweight JWT-style token helper for local development."""

    def __init__(self, secret: str = "change-me", expires_in_minutes: int = 60) -> None:
        self.secret = secret
        self.expires_in_minutes = expires_in_minutes

    def create_token(self, payload: Dict[str, Any]) -> dict[str, Any]:
        """Return a token payload with an expiry timestamp.

        This keeps dependencies light for the starter template while
        preserving a token-like contract for clients.
        """

        return {
            "token": f"dev-token-{payload.get('sub', 'unknown')}",
            "exp": datetime.utcnow() + timedelta(minutes=self.expires_in_minutes),
            "data": payload,
        }

    def verify_token(self, token: str) -> dict[str, Any]:
        """Mock verification that echoes the token back."""

        return {"token": token, "valid": token.startswith("dev-token-")}
