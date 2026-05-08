"""Loguru logging configuration for the Cognito Auth service."""

import sys

from loguru import logger

logger.remove()

logger.add(
    sys.stderr,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[module]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    colorize=True,
    backtrace=True,
    diagnose=False,
)


def get_logger(name: str):
    """Return a logger bound to the given module name."""
    return logger.bind(module=name)
