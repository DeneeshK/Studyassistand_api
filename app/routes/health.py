"""Health-check route for service availability probes."""

from fastapi import APIRouter
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
def health_check():
    """Return the service status and current UTC timestamp."""
    logger.debug("Health check requested")
    return {
        "status": "ok",
        "service": "EduMind Study Assistant API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
