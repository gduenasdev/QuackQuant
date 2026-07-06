from fastapi import APIRouter

from app.api.todos import not_implemented
from app.schemas import PreferencesUpdate

router = APIRouter()


@router.get("/me")
def current_user() -> None:
    # TODO: Resolve the user from the verified session dependency; never trust a user ID header.
    not_implemented("Load the authenticated user from a verified session.")


@router.get("/dashboard")
def dashboard() -> None:
    # TODO: Compose a bounded summary from portfolios, recent runs, signals, and alerts.
    not_implemented("Build an authenticated, cached dashboard projection.")


@router.get("/notifications")
def notifications() -> None:
    # TODO: Add cursor pagination and user-scoped database queries.
    not_implemented("Store and paginate user-scoped notifications.")


@router.patch("/preferences")
def update_preferences(payload: PreferencesUpdate) -> None:
    # TODO: Persist a partial update and validate supported timezone identifiers.
    not_implemented("Validate and persist user preferences.")

