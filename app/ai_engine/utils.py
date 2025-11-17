import logging
from functools import lru_cache


@lru_cache(maxsize=1)
def get_logger() -> logging.Logger:
    logger = logging.getLogger("ai-engine")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s][AI] %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_training(message: str) -> None:
    get_logger().info(message)
