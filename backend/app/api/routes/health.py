from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/ready", summary="Dependency readiness check")
def readiness() -> dict[str, str]:
    # TODO: Verify market-data and broker adapters once they are configured.
    return {"status": "ready", "note": "No external dependencies configured yet"}
