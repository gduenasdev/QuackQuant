from typing import NoReturn

from fastapi import HTTPException, status


def not_implemented(strategy: str) -> NoReturn:
    """Fail loudly until an endpoint has a secure, tested implementation."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"status": "not_implemented", "strategy": strategy},
    )

