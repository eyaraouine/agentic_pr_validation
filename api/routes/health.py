# Health Check Routes

from fastapi import APIRouter, Depends
from typing import Dict, Any
import psutil
import asyncio
from datetime import datetime

from api.models import HealthCheckResponse
from src.config.settings import Settings
from src.utils.logger import setup_logger

router = APIRouter()
settings = Settings()
logger = setup_logger("api.routes.health")


@router.get("/", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Basic health check endpoint

    Returns:
        Health status response
    """
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
        services={
            "api": "healthy",
            "crew": "healthy"
        }
    )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with system metrics

    Returns:
        Detailed health status including system metrics
    """
    # Check various services
    services_status = await check_services()

    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # Get process info
    process = psutil.Process()
    process_info = {
        "cpu_percent": process.cpu_percent(interval=1),
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        "threads": process.num_threads(),
        "open_files": len(process.open_files()),
        "connections": len(process.connections())
    }

    return {
        "status": "healthy" if all(v == "healthy" for v in services_status.values()) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.API_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": services_status,
        "system_metrics": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_mb": round(memory.total / 1024 / 1024, 2),
                "available_mb": round(memory.available / 1024 / 1024, 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": disk.percent
            }
        },
        "process_info": process_info,
        "configuration": {
            "crew_verbose": settings.CREW_VERBOSE,
            "validation_timeout": settings.VALIDATION_TIMEOUT,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "cache_enabled": settings.ENABLE_CACHE,
            "openai_type": settings.OPENAI_API_TYPE or "standard",
            "azure_deployment": settings.AZURE_OPENAI_DEPLOYMENT_NAME if settings.OPENAI_API_TYPE == "azure" else None
        }
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe for Kubernetes

    Returns:
        Readiness status
    """
    try:
        # Check if all required services are available
        services_status = await check_services()

        # Check if critical services are healthy
        critical_services = ["api", "crew"]
        all_critical_healthy = all(
            services_status.get(service) == "healthy"
            for service in critical_services
        )

        if all_critical_healthy:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "reason": "Critical services unhealthy",
                "services": services_status
            }

    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": str(e)
        }


@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe for Kubernetes

    Returns:
        Liveness status
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": psutil.Process().create_time()
    }


async def check_services() -> Dict[str, str]:
    """
    Check the health of various services

    Returns:
        Dictionary of service statuses
    """
    services_status = {}

    # Check API
    services_status["api"] = "healthy"

    # Check CrewAI
    try:
        # Simple check - try to import crew
        from src.crew.pr_validation_crew import PRValidationCrew
        services_status["crew"] = "healthy"
    except Exception as e:
        logger.error(f"CrewAI health check failed: {str(e)}")
        services_status["crew"] = "unhealthy"

    # Check database if configured
    if not settings.USE_IN_MEMORY_JOBS and settings.DATABASE_URL:
        services_status["database"] = await check_database()

    # Check Redis if configured
    if settings.REDIS_URL:
        services_status["redis"] = await check_redis()

    # Check OpenAI API
    services_status["openai"] = await check_openai()

    return services_status


async def check_database() -> str:
    """Check database connectivity"""
    try:
        # Import here to avoid circular dependencies
        from sqlalchemy import create_engine, text

        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        return "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return "unhealthy"


async def check_redis() -> str:
    """Check Redis connectivity"""
    try:
        import redis

        r = redis.from_url(settings.REDIS_URL)
        r.ping()

        return "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return "unhealthy"


async def check_openai() -> str:
    """Check OpenAI API connectivity"""
    try:
        if settings.OPENAI_API_TYPE == "azure":
            import openai

            # Configure Azure OpenAI
            openai.api_type = "azure"
            openai.api_key = settings.AZURE_OPENAI_API_KEY
            openai.api_base = settings.AZURE_OPENAI_ENDPOINT
            openai.api_version = settings.AZURE_OPENAI_API_VERSION

            # Test Azure OpenAI
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                engine=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )

            return "healthy" if response else "unhealthy"
        else:
            import openai

            # Set API key
            openai.api_key = settings.OPENAI_API_KEY

            # Try a simple API call with minimal tokens
            response = await asyncio.to_thread(
                openai.ChatCompletion.create,
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )

            return "healthy" if response else "unhealthy"
    except Exception as e:
        logger.error(f"OpenAI health check failed: {str(e)}")
        return "unhealthy"