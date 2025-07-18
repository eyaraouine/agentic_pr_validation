# Logging Middleware

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

from src.utils.logger import setup_logger, log_structured

logger = setup_logger("api.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request and response details

        Args:
            request: Incoming request
            call_next: Next middleware or endpoint

        Returns:
            Response object
        """
        # Generate request ID
        request_id = str(uuid.uuid4())

        # Start timer
        start_time = time.time()

        # Log request
        log_structured(
            logger,
            "info",
            f"Request started: {request.method} {request.url.path}",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ['authorization', 'x-api-key']}
        )

        # Add request ID to request state
        request.state.request_id = request_id

        # Process request
        response = None
        error = None

        try:
            response = await call_next(request)
        except Exception as e:
            error = e
            log_structured(
                logger,
                "error",
                f"Request failed: {type(e).__name__}",
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e),
                duration=time.time() - start_time
            )
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Log response
            if response:
                log_structured(
                    logger,
                    "info" if response.status_code < 400 else "warning",
                    f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration=duration,
                    duration_ms=round(duration * 1000, 2)
                )

                # Add request ID to response headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Response-Time"] = f"{round(duration * 1000, 2)}ms"

        return response


class PerformanceLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for detailed performance logging"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log detailed performance metrics

        Args:
            request: Incoming request
            call_next: Next middleware or endpoint

        Returns:
            Response object
        """
        # Skip for health checks
        if request.url.path == "/api/health":
            return await call_next(request)

        # Detailed timing
        timings = {
            "start": time.time(),
            "request_read": 0,
            "processing": 0,
            "response_write": 0,
            "total": 0
        }

        # Read request body if present
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            timings["request_read"] = time.time() - timings["start"]

            # Create new request with body
            async def receive() -> Message:
                return {"type": "http.request", "body": body}

            request._receive = receive

        # Process request
        processing_start = time.time()
        response = await call_next(request)
        timings["processing"] = time.time() - processing_start

        # Calculate total time
        timings["total"] = time.time() - timings["start"]
        timings["response_write"] = timings["total"] - timings["request_read"] - timings["processing"]

        # Log performance metrics
        if timings["total"] > 1.0:  # Log slow requests
            log_structured(
                logger,
                "warning",
                f"Slow request detected: {request.method} {request.url.path}",
                request_id=getattr(request.state, "request_id", "unknown"),
                method=request.method,
                path=request.url.path,
                timings={k: round(v * 1000, 2) for k, v in timings.items()},
                slow_request=True
            )

        return response