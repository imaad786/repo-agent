import tomllib


class ToMlUtils:
    @staticmethod
    def _load_toml(file_path: str) -> dict:
        """Load a TOML file and return it as a dictionary."""
        with open(file_path, "rb") as f:
            return tomllib.load(f)

    @staticmethod
    def get(file_path: str, *keys, default=None):
        """
        Generic getter for nested keys.
        Example:
            PromptUtils.get("agent_config.toml", "agent", "tools", "general_tool_system_message")
        """
        config = ToMlUtils._load_toml(file_path)
        data = config
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data
