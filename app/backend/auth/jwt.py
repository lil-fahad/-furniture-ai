from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

DEFAULT_TTL_MINUTES = 60


class JWTAuth:
    def __init__(self, secret_key: Optional[str] = None, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> None:
        self.secret_key = secret_key or os.environ.get("JWT_SECRET", "dev-secret")
        self.ttl_minutes = ttl_minutes

    def issue_token(self, subject: str) -> Dict[str, str]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.ttl_minutes)
        return {
            "token": token,
            "subject": subject,
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        }

    def validate(self, token: str) -> bool:
        # In a real system this would decode and verify the token signature.
        return bool(token and len(token) > 20 and self.secret_key)
