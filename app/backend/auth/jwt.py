from dataclasses import dataclass
from typing import Optional

from app.backend.utils.logger import get_logger


@dataclass
class JWTAuth:
    secret: str = "local-dev-secret"

    def __post_init__(self) -> None:
        self._logger = get_logger(__name__)

    def validate(self, token: Optional[str]) -> bool:
        if not token:
            self._logger.warning("Missing token")
            return False
        is_valid = token == self.secret
        if not is_valid:
            self._logger.warning("Invalid token provided")
        return is_valid
