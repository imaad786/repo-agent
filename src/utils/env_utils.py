import os

from dotenv import load_dotenv


class EnvUtils:
    @staticmethod
    def load_env():
        dotenv_path = EnvUtils.get_env_file_path()
        load_dotenv(dotenv_path)

    @staticmethod
    def is_local_environment() -> bool:
        environment = os.getenv('APP_PROFILE', 'local').lower()
        return environment in ["local"]

    @staticmethod
    def get_env_file_path():
        environment = os.getenv('APP_PROFILE', 'local')
        dotenv_path = f'.env.{environment}'
        return dotenv_path
