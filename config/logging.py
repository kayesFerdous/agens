# config/logging.py — centralized logging configuration
import logging

LOG_FORMAT = "%(levelname)s | %(name)s | %(message)s"
LOG_LEVEL = logging.INFO


def setup_logging(level: int = LOG_LEVEL, fmt: str = LOG_FORMAT) -> None:
    logging.basicConfig(level=level, format=fmt)
