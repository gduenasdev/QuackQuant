# API implementation strategy

The route scaffold defines the intended HTTP surface, not production behavior. All unfinished
routes deliberately return `501 Not Implemented`.

## Phase 1 — foundation and landing page

- Add SQLAlchemy/Alembic and PostgreSQL connection/session management.
- Create append-only audit events plus users, sessions, and waitlist tables.
- Choose an OIDC authentication provider and implement a secure HttpOnly session.
- Add `POST /waitlist` only after database persistence, rate limiting, bot protection, and consent
  text are ready.
- Add structured logs, request IDs, error reporting, and production CORS configuration.

Exit criterion: migrations are reproducible; authentication and authorization tests pass; no
endpoint trusts a caller-provided user ID.

## Phase 2 — research data and strategies

- Define provider interfaces for quotes, candles, and news so vendors remain replaceable.
- Confirm market-data display, storage, and redistribution rights before retaining responses.
- Cache quotes briefly and label every response with source and freshness timestamps.
- Store immutable strategy revisions; backtests reference a revision, never a mutable strategy.
- Add cursor pagination and ownership-scoped queries to every collection/detail endpoint.

Exit criterion: the same versioned inputs reproduce the same strategy/backtest configuration.

## Phase 3 — asynchronous backtests and agents

- Add Redis plus Celery only when a real job cannot safely finish within one HTTP request.
- Persist each job before enqueueing it; send only the job ID through the queue.
- Make jobs idempotent, retry-safe, cancellable at checkpoints, and subject to compute quotas.
- Store summary results in PostgreSQL and large artifacts in object storage.
- Add authenticated Server-Sent Events for progress; polling remains a fallback.
- Record prompts, tools, models, inputs, policies, decisions, and outputs with secrets redacted.

Exit criterion: worker restarts do not duplicate runs or lose their durable status.

## Phase 4 — paper broker integration

- Use the broker's OAuth flow and encrypt tokens; never expose credentials to the browser.
- Build a provider adapter and a local append-only order ledger/state machine.
- Implement preview-first orders with buying-power, exposure, price-age, and market-state checks.
- Require idempotency keys and persist order intent before calling the broker.
- Verify webhook signatures over raw request bodies, reject replay, deduplicate, then process.
- Reconcile ambiguous submissions and cancellations against the broker's authoritative state.

Exit criterion: paper-only execution survives retries, webhook duplication, timeouts, and restarts.

## Live trading gate

Live execution is intentionally outside this scaffold. It should require a separate threat model,
legal/compliance review, kill switch, restricted permissions, monitoring/alerting, recovery drills,
and independent testing of risk limits. Do not enable it by changing a single configuration flag.

