import logging
from typing import Any


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure a shared logger for the project."""

    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    return logging.getLogger("furniture_ai")


def log(message: str, *args: Any, **kwargs: Any) -> None:
    """Log a message through the shared logger."""

    logger = logging.getLogger("furniture_ai")
    logger.info(message, *args, **kwargs)
