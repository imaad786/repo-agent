import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from .env_utils import EnvUtils


class LoggingUtils:
    @staticmethod
    def configure_logging(add_file_handler: bool = True):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        logging_level = logging.DEBUG if EnvUtils.is_local_environment() else logging.INFO

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s [pid:%(process)d] - %(name)s - %(message)s'
        ))
        console_handler.setLevel(logging_level)
        logger.addHandler(console_handler)

        if add_file_handler:
            os.makedirs('logs', exist_ok=True)
            file_handler = RotatingFileHandler(
                'logs/app.log', maxBytes=100000, backupCount=50
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s [pid:%(process)d] - %(name)s - %(message)s'
            ))
            file_handler.setLevel(logging_level)
            logger.addHandler(file_handler)

        logger.info(
            f"Logging configured. Environment: {'local' if EnvUtils.is_local_environment() else 'non-local'}"
        )
        return logger
