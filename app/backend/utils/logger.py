import logging
from typing import Optional


DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def configure_logger(level: int = DEFAULT_LOG_LEVEL, handler: Optional[logging.Handler] = None) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, handlers=[handler] if handler else None)


def get_logger(name: str = "furniture_ai") -> logging.Logger:
    if not logging.getLogger().handlers:
        configure_logger()
    return logging.getLogger(name)
