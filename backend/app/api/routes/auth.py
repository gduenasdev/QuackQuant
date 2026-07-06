from fastapi import APIRouter, Response

from app.api.todos import not_implemented
from app.schemas import LoginRequest

router = APIRouter()


@router.post("/login")
def login(payload: LoginRequest) -> None:
    # TODO: Integrate an OIDC provider; exchange credentials for a secure, HttpOnly session.
    # TODO: Add brute-force protection, audit logging, and generic failure messages.
    not_implemented("Integrate OIDC and issue a secure server-side session.")


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    # TODO: Revoke the server-side session and expire its cookie.
    not_implemented("Revoke the authenticated session and clear its cookie.")

