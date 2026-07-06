from fastapi import APIRouter

from app.api.todos import not_implemented
from app.schemas import ContactCreate, WaitlistCreate

router = APIRouter()


@router.post("/waitlist", status_code=202)
def join_waitlist(payload: WaitlistCreate) -> None:
    # TODO: Normalize/validate email, require consent, hash request IP for abuse controls,
    # rate-limit by IP/email, and insert with a unique normalized-email constraint.
    # TODO: Send confirmation asynchronously and avoid revealing whether an email already exists.
    not_implemented("Persist a consented, rate-limited waitlist signup and confirm asynchronously.")


@router.post("/contact", status_code=202)
def contact(payload: ContactCreate) -> None:
    # TODO: Add bot protection, per-IP/email rate limits, content sanitization, and a durable inbox.
    # TODO: Queue notifications; never place untrusted form input directly into email headers.
    not_implemented("Validate, rate-limit, persist, and asynchronously notify on contact messages.")

