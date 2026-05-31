from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "EduMind Study Assistant API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
