import datetime
import logging
import uuid

from fastapi import Request, FastAPI


def add_request_logger_middleware(application: FastAPI):
    @application.middleware("http")
    async def request_response_logger(request: Request, call_next):
        start_time = datetime.datetime.now(datetime.UTC)

        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        correlation_id = request.headers.get("x-correlation-id", str(uuid.uuid4()))

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        logging.info(
            f"Incoming Request: {request.method} {request.url} | Request ID: {request_id} | Correlation ID: {correlation_id} | Client: {request.client.host}"
        )

        response = await call_next(request)

        end_time = datetime.datetime.now(datetime.UTC)
        process_time = (end_time - start_time).total_seconds()
        logging.info(
            f"Outgoing Response: {response.status_code} | Request ID: {request_id} | Correlation ID: {correlation_id} | Time: {process_time:.2f}s"
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id

        return response
