# API Gateway for PR Validation System
# FastAPI application handling validation requests from Azure DevOps

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
from datetime import datetime
import asyncio
from typing import Optional

from api.routes import health, validation
from api.middleware.auth import verify_api_key
from api.middleware.logging import LoggingMiddleware
from src.config.settings import Settings
from src.utils.logger import setup_logger

# Initialize settings and logger
settings = Settings()
logger = setup_logger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager
    """
    # Startup
    logger.info("Starting PR Validation API Gateway...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"API Version: {settings.API_VERSION}")

    # Initialize any required connections or resources
    yield

    # Shutdown
    logger.info("Shutting down PR Validation API Gateway...")


# Create FastAPI application
app = FastAPI(
    title="PR Validation API",
    description="API Gateway for automated pull request validation using CrewAI",
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add custom logging middleware
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(
    health.router,
    prefix="/api/health",
    tags=["health"]
)

app.include_router(
    validation.router,
    prefix="/api/v1",
    tags=["validation"],
    dependencies=[Depends(verify_api_key)]
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom HTTP exception handler
    """
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    General exception handler for unhandled errors
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "status_code": 500,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        }
    )


@app.get("/")
async def root():
    """
    Root endpoint
    """
    return {
        "message": "PR Validation API Gateway",
        "version": settings.API_VERSION,
        "status": "operational",
        "docs": f"/api/docs" if settings.ENVIRONMENT != "production" else "disabled"
    }


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower()
    )