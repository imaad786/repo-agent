from .env_utils import EnvUtils
from .logging_utils import LoggingUtils
from .settings import Settings


def bootstrap_application():
    EnvUtils.load_env()

    LoggingUtils.configure_logging(add_file_handler=False)

    settings = Settings()

    return settings
