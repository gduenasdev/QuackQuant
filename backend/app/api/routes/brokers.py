from fastapi import APIRouter, Header, Request, Response

from app.api.todos import not_implemented
from app.schemas import BrokerConnectionCreate, OrderCreate, OrderPreviewRequest

router = APIRouter()


@router.get("/broker-connections")
def list_broker_connections() -> None:
    # TODO: Return provider and status only; never return access or refresh tokens.
    not_implemented("List redacted, user-owned broker connections.")


@router.post("/broker-connections", status_code=201)
def create_broker_connection(payload: BrokerConnectionCreate) -> None:
    # TODO: Exchange OAuth codes server-side and encrypt tokens with a managed encryption key.
    not_implemented("Complete server-side OAuth and encrypt broker credentials.")


@router.delete("/broker-connections/{connection_id}", status_code=204, response_class=Response)
def delete_broker_connection(connection_id: str) -> None:
    # TODO: Revoke upstream tokens before deleting the local encrypted credentials.
    not_implemented("Revoke the provider token and remove the connection.")


@router.get("/portfolio")
def portfolio() -> None:
    # TODO: Query the selected owned connection and include provider/freshness timestamps.
    not_implemented("Load a fresh portfolio through an authorized broker adapter.")


@router.get("/orders")
def list_orders() -> None:
    # TODO: Reconcile provider orders into a user-scoped local ledger.
    not_implemented("Return reconciled orders from the local immutable ledger.")


@router.post("/orders/preview")
def preview_order(payload: OrderPreviewRequest) -> None:
    # TODO: Check buying power, limits, market state, exposure, and stale prices.
    # TODO: Return a short-lived signed preview token; do not place an order here.
    not_implemented("Run risk checks and issue a short-lived order preview.")


@router.post("/orders", status_code=202)
def create_order(payload: OrderCreate, idempotency_key: str = Header()) -> None:
    # TODO: Require a valid preview, explicit acknowledgement, paper mode, and idempotency key.
    # TODO: Persist intent before provider submission and reconcile ambiguous responses.
    not_implemented("Submit an approved paper order through an idempotent state machine.")


@router.post("/orders/{order_id}/cancel", status_code=202)
def cancel_order(order_id: str) -> None:
    # TODO: Treat cancel as a request; reconcile the final state with the provider.
    not_implemented("Request cancellation and reconcile the provider result.")


@router.post("/webhooks/broker", status_code=202)
async def broker_webhook(request: Request) -> None:
    # TODO: Verify signature against raw bytes before parsing; reject stale/replayed events.
    # TODO: Deduplicate by provider event ID, persist first, then process asynchronously.
    not_implemented("Verify, deduplicate, persist, and asynchronously process broker events.")
