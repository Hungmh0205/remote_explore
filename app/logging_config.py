import logging
import sys
from logging.handlers import RotatingFileHandler
from .config import settings

def setup_logging():
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console Handler (stdout)
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler (Rotating)
    if settings.log_file:
        # Max 2MB per file, keep only 1 backup (total ~4MB)
        f_handler = RotatingFileHandler(settings.log_file, maxBytes=2*1024*1024, backupCount=1, encoding='utf-8')
        f_handler.setLevel(logging.INFO)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    # Uvicorn Access Logs (capture them too)
    logging.getLogger("uvicorn.access").handlers = [c_handler, f_handler]
    logging.getLogger("uvicorn.error").handlers = [c_handler, f_handler]

    logging.info(f"Logging configured. Writing to {settings.log_file}")
