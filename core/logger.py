import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logger(name: str, log_file: str = "logs/app.log") -> logging.Logger:
    """Configure and return a logger with console and UTF-8 file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    raw_path = Path(log_file)
    log_path = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    resolved_log_path = log_path.resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)

    if not any(type(h) is logging.StreamHandler for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    has_matching_file_handler = False
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            if Path(handler.baseFilename).resolve() == resolved_log_path:
                has_matching_file_handler = True
            else:
                handler.close()
                logger.removeHandler(handler)

    if not has_matching_file_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
