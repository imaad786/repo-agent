import cowsay
import uvicorn

from src import settings
from src.utils.env_utils import EnvUtils

if __name__ == "__main__":
    cowsay.tux("Starting Taazaa AI Agent SVC...")

    uvicorn.run(
        "src.app:application",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level="debug" if EnvUtils.is_local_environment() else "info",
        timeout_keep_alive=10 * 60,  # 10 Minutes,
        reload=EnvUtils.is_local_environment(),
        reload_dirs=["src"] if EnvUtils.is_local_environment() else None,
    )



