from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from .agent import initialize_and_get_agent
from .exceptions.global_handler import register_global_exception_handlers
from .middlewares.request_logger_middleware import add_request_logger_middleware
from .routes import hello_world_router, agent_router
from .db.context import DbContext
from .services import session_cache_service
from . import entities


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent_instance = None
    try:
        DbContext.initialize()
        agent_instance = await initialize_and_get_agent()
        await agent_instance.startup()
        app.state.agent = agent_instance
        await agent_instance.save_graph_png()

        # Start background cache cleanup task
        await session_cache_service.start_background_cleanup()

        yield

    finally:
        # Stop background cache cleanup task
        await session_cache_service.stop_background_cleanup()

        if agent_instance:
            await agent_instance.shutdown()
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

    register_global_exception_handlers(app)
    add_request_logger_middleware(app)

    return app


application = setup_application()
