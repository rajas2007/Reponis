import logging
import sys

from src.core.config import settings


def setup_logging() -> None:
    log_level = logging.getLevelName(settings.LOG_LEVEL.upper())

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence verbose loggers if needed
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
