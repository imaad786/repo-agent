from typing import Tuple


def parse_model_id(model_id: str) -> Tuple[str, str]:
    """
    Parse a model ID string in "provider:model_name" format.

    Returns:
        Tuple of (provider, model_name).
        If no colon is found, returns ("unknown", model_id).
    """
    if not model_id:
        return ("unknown", "unknown")
    parts = model_id.split(":", 1)
    if len(parts) == 2:
        return (parts[0].strip(), parts[1].strip())
    return ("unknown", model_id.strip())
