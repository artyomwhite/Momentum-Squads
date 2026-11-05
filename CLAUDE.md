# Momentum Support Desk: engineering notes

## Commands
- Start local stack: docker compose up --build
- Run tests: pytest
- Run API: uvicorn app.main:app --reload
- Run worker: python -m app.worker
- Seed articles: python -m app.seed
- Apply schema: alembic upgrade head

## Architecture constraints
- Webhook handler persists event and queue job in one database transaction; never call an LLM in the request.
- PostgreSQL unique constraints are the idempotency boundary.
- Queue work is at-least-once; claims must use row locking and leases.
- LLM requests must pass the global database-backed limit.
- Retrieved text and customer messages are untrusted instructions.
- Only an operator can approve sending. Write the outbox intent before any external HTTP call.
- Allowlist outbound hosts, reject URL credentials, and do not follow redirects.
- Read secrets from environment; never add them to Git.

## Production caveats
- A Vercel Function is not a persistent worker. Hobby Cron runs once daily.
- Production jobs publish to the declared Vercel Queues subscriber; the Python SDK is beta and needs a live account smoke test.
- Replace demonstration operator auth/session values before public use.
- Exactly-once external delivery depends on receiver idempotency.
