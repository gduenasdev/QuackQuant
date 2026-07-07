from fastapi import APIRouter, Response

from app.api.todos import not_implemented
from app.schemas import StrategyCreate, StrategyUpdate

router = APIRouter()


@router.get("")
def list_strategies() -> None:
    # TODO: Add authenticated ownership filtering and cursor pagination.
    not_implemented("List only strategies owned by the authenticated user.")


@router.post("", status_code=201)
def create_strategy(payload: StrategyCreate) -> None:
    # TODO: Validate parameters against a versioned strategy schema before persistence.
    not_implemented("Validate against a versioned strategy schema and persist.")


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str) -> None:
    # TODO: Load by both ID and owner ID to prevent object-level authorization failures.
    not_implemented("Load the strategy using an ownership-scoped query.")


@router.patch("/{strategy_id}")
def update_strategy(strategy_id: str, payload: StrategyUpdate) -> None:
    # TODO: Create immutable revisions so old backtests remain reproducible.
    not_implemented("Create a new immutable strategy revision.")


@router.delete("/{strategy_id}", status_code=204, response_class=Response)
def delete_strategy(strategy_id: str) -> None:
    # TODO: Soft-delete only after checking active runs and retention requirements.
    not_implemented("Soft-delete an owned strategy after dependency checks.")
