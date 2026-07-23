from fastapi import APIRouter

from app.api.routes import (
    agents,
    health,
    scanner,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
api_router.include_router(agents.router, tags=["agents"])
