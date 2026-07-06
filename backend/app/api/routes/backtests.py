from fastapi import APIRouter

from app.api.todos import not_implemented
from app.schemas import BacktestCreate

router = APIRouter()


@router.post("", status_code=202)
def create_backtest(payload: BacktestCreate) -> None:
    # TODO: Snapshot strategy/data versions, persist a queued job, then enqueue its ID.
    # TODO: Make task execution idempotent and enforce per-user compute quotas.
    not_implemented("Persist a reproducible job and enqueue it for a worker.")


@router.get("/{backtest_id}")
def get_backtest(backtest_id: str) -> None:
    # TODO: Return ownership-scoped status, progress, timestamps, and sanitized failures.
    not_implemented("Return authorized job status and progress.")


@router.get("/{backtest_id}/results")
def get_backtest_results(backtest_id: str) -> None:
    # TODO: Store summary metrics in PostgreSQL and large artifacts in object storage.
    not_implemented("Return versioned metrics and signed artifact references.")

