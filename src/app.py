from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .agent.agent_registry import initialize_registry, shutdown_registry
from .exceptions.global_handler import register_global_exception_handlers
from .middlewares.request_logger_middleware import add_request_logger_middleware
from .routes import hello_world_router, agent_router, analysis_router
from .workers import start_analysis_worker, stop_analysis_worker
from .db.context import DbContext
from .services import session_cache_service
from . import entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = None
    try:
        DbContext.initialize()

        # Initialize agent registry with all agents preloaded
        registry = await initialize_registry()
        app.state.registry = registry

        # Start background cache cleanup task
        await session_cache_service.start_background_cleanup()

        # Start analysis background worker
        await start_analysis_worker()

        yield

    finally:
        # Stop analysis background worker
        await stop_analysis_worker()

        # Stop background cache cleanup task
        await session_cache_service.stop_background_cleanup()

        # Shutdown the agent registry
        await shutdown_registry()

        await DbContext.dispose_engine()


def setup_application():
    app = FastAPI(
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        title="Taazaa AI Agent Service",
        description="Code Intelligence Agent Service for Taazaa AI Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS Configuration - Configure allowed origins from environment variables
    from . import settings
    allowed_origins = getattr(settings, 'cors_allowed_origins', '*')
    if allowed_origins == '*':
        allowed_origins = ["*"]
    elif isinstance(allowed_origins, str):
        allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "service": "Taazaa-AI-Agent-SVC"}

    # Register routers
    app.include_router(hello_world_router, prefix="/api/v1/hello-world", tags=["Hello World"])
    app.include_router(agent_router, prefix="/api/v1", tags=["Code Intelligence Agent"])
    app.include_router(analysis_router, prefix="/api/v1", tags=["Analysis"])

    register_global_exception_handlers(app)
    add_request_logger_middleware(app)

    return app


application = setup_application()

