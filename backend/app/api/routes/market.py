from fastapi import APIRouter, Query

from app.api.todos import not_implemented

router = APIRouter()


@router.get("/quotes")
def quotes(symbols: list[str] = Query(min_length=1, max_length=100)) -> None:
    # TODO: Normalize symbols, query a licensed provider, cache briefly, and expose data age.
    not_implemented("Add a licensed market-data adapter with caching and freshness metadata.")


@router.get("/candles/{symbol}")
def candles(symbol: str, interval: str = "1d") -> None:
    # TODO: Use an interval allow-list, cursor/date bounds, caching, and adjusted-price semantics.
    not_implemented("Add bounded historical candle queries through a provider adapter.")


@router.get("/news")
def news(symbol: str | None = None) -> None:
    # TODO: Respect news redistribution terms; deduplicate and retain source attribution.
    not_implemented("Add a licensed news provider while preserving attribution.")


@router.get("/signals")
def signals() -> None:
    # TODO: Return versioned, user-authorized signals with timestamps and explanatory metadata.
    not_implemented("Persist and paginate versioned signals.")


@router.get("/signals/{signal_id}")
def signal(signal_id: str) -> None:
    # TODO: Enforce ownership/entitlement before returning model or strategy output.
    not_implemented("Load one authorized signal and its audit metadata.")

