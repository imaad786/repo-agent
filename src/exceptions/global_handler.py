import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from src.utils.env_utils import EnvUtils


async def global_exception_handler(request: Request, exc: Exception):
    logging.error(
        f"Unhandled Exception: Request ID: {request.state.request_id} | "
        f"Correlation ID: {request.state.correlation_id} | "
        f"Path: {request.url.path} | Exception: {exc.__class__.__name__}",
        exc_info=True
    )

    # Don't expose internal error details in production
    error_detail = str(exc) if EnvUtils.is_local_environment() else "An internal error occurred"

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "detail": error_detail,
                "request_id": request.state.request_id
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logging.error(
        f"HTTP Exception: Request ID: {request.state.request_id} | "
        f"Correlation ID: {request.state.correlation_id} | "
        f"Status: {exc.status_code} | Detail: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "request_id": request.state.request_id
            }
        },
    )


def register_global_exception_handlers(application: FastAPI):
    application.add_exception_handler(Exception, global_exception_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
