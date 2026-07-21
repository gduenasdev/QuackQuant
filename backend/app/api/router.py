from fastapi import APIRouter

from app.api.routes import (
    agents,
    auth,
    backtests,
    brokers,
    dashboard,
    health,
    market,
    public,
    scanner,
    strategies,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(public.router, tags=["public"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard.router, tags=["account"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(scanner.router, prefix="/scanner", tags=["scanner"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(brokers.router, tags=["brokers"])
