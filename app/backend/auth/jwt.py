import os
import secrets
from datetime import datetime, timedelta

DEFAULT_TTL_MINUTES = 60


class JWTAuth:
    def __init__(self, secret_key: str | None = None, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> None:
        self.secret_key = secret_key or os.environ.get("JWT_SECRET", "dev-secret")
        self.ttl_minutes = ttl_minutes

    def issue_token(self, subject: str) -> dict[str, str]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=self.ttl_minutes)
        return {"token": token, "subject": subject, "expires_at": expires_at.isoformat() + "Z"}

    def validate(self, token: str) -> bool:
        # In a real system this would decode and verify the token signature.
        return bool(token and len(token) > 20 and self.secret_key)
