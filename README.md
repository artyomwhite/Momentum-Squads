# Momentum Support Desk

AI-assisted support triage for a fictional project analytics SaaS. The service stores helpdesk webhooks idempotently, queues work in PostgreSQL, creates an evidence-based draft, and waits for an operator before sending anything.

## Architecture

\`\`\`mermaid
flowchart LR
  H[Helpdesk webhook] -->|event and job transaction| DB[(PostgreSQL)]
  DB --> W[Worker: lease and SKIP LOCKED]
  W -. local .-> L[Compose worker]
  W -. Vercel .-> Q[Vercel Queues subscriber]
  W --> K[PostgreSQL full-text retrieval]
  K --> AI[OpenAI or no-key fallback]
  AI --> DB
  DB --> UI[Operator dashboard]
  UI -->|approval and outbox transaction| O[Outbox delivery]
  O -->|Idempotency-Key| HD[Helpdesk or mock]
\`\`\`

## Stack and project layout

Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL, httpx, Jinja2, pytest and Docker Compose. HTTP routes are under app/api; retrieval, AI, worker and Helpdesk adapters are under app/services; models are in app/models.py; app/worker.py runs the separate local queue worker; operator HTML and CSS are under app/templates and app/static.

## Features and data

- Event IDs and one-job-per-ticket unique constraints prevent duplicate webhook deliveries.
- PostgreSQL queue workers claim jobs with row locks and SKIP LOCKED, leases, recovery and bounded exponential retries.
- Knowledge articles use PostgreSQL full-text search with a local fallback implementation.
- OpenAI JSON draft generation is constrained to retrieved source IDs; user and KB text are untrusted prompt data.
- PostgreSQL per-minute slots coordinate a service-wide 60 requests/minute LLM cap.
- Operator can edit, approve or reject; generation never sends a response.
- Approval inserts a transactional outbox row with a stable Idempotency-Key before delivery.
- Mock Helpdesk returns 201, supports idempotent retries and test modes.

Tables: tickets (event and draft/status), jobs (durable task lease/retries), articles (knowledge content), rate_slots (global LLM budget), outbox (approved delivery intent).

## Local setup

Copy .env.example to .env, then run:

\`\`\`sh
docker compose up --build
\`\`\`

Open http://localhost:8000. Demo login is operator / change-me; change it and SESSION_SECRET before exposing the app.

Send a webhook:

\`\`\`sh
curl -X POST http://localhost:8000/webhooks/helpdesk -H "Content-Type: application/json" -d '{"event_id":"evt_8f2a","ticket_id":"T-1042","customer_email":"user@example.com","message":"Cannot export a report to PDF","reply_url":"http://mock-helpdesk:8001/tickets/T-1042/replies"}'
\`\`\`

Health is GET /health; readiness is GET /ready; knowledge list/search are GET /knowledge and GET /knowledge/search?q=PDF%20export. The mock is on port 8001.

## Queue and idempotency

Webhook handling validates the payload and allowlisted reply host, then commits the event and queue row together. It does not call the LLM. Workers use SKIP LOCKED so competing workers do not claim the same ready row. A lease allows another worker to recover work after a process crash. Retry count is bounded.

The local compose stack uses a long-running worker. Vercel Functions are request-scoped, not a persistent Python worker. The current Vercel Python runtime supports FastAPI. Vercel Queues provides push consumers, at-least-once delivery and retries; its Python SDK is currently beta. Vercel Hobby Cron runs only once per day, so Cron cannot provide near-real-time processing. Production uses the Vercel Queues subscriber declared in pyproject.toml and Neon PostgreSQL, with durable database state retained for idempotency and recovery. Queue publishing waits for Vercel Queue acceptance; if it fails, the webhook returns 503 so the sender can retry the same event. Validate the external queue and Neon account before production traffic.

## AI and fallback

With OPENAI_API_KEY set, the worker calls the configured OpenAI-compatible Chat Completions API and validates the JSON response. Only citations matching retrieved article IDs are retained. All drafts require human review. Confidence is a heuristic, not a statistically calibrated probability.

Without a key, the application makes an unauthenticated GET request to the configured provider's /models endpoint. A 401 is expected and is not fatal. The fallback waits asynchronously for 5–30 seconds and returns a deterministic response using the same output structure. Provider connectivity errors are logged but do not prevent the fallback.

## Operator and Helpdesk

The session-protected dashboard lists customer, message, status, draft, sources and timestamps. Operators can edit drafts, approve and send, or reject. The shared password is a demonstration login; use a managed identity provider and HTTPS-only cookies before public production.

Outbound reply hosts must be explicitly allowlisted. Redirects are disabled to reduce SSRF risk. The mock deduplicates repeated Idempotency-Key values and supports ?mode=fail and ?mode=timeout. A timeout after a remote server has accepted a reply is safe to retry only if the server honors the idempotency key. Exactly-once cannot be guaranteed for a receiver without deduplication support.

## Environment variables

See .env.example for DATABASE_URL, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, operator credentials, session secret, allowed Helpdesk hosts, fallback delay, LLM limit and worker lease/retry settings. Keep .env out of Git.

## Tests

Run pytest. Tests do not need an OpenAI key. PostgreSQL integration tests are needed to verify concurrent delivery, SKIP LOCKED claims and atomic global rate limiting against the real database backend.

## Vercel and Neon deployment

The test deployment is available at https://momentum-squads.vercel.app/. It is protected by Vercel team authentication; sign in to the Vercel team if prompted, then use the app credentials below.

**Test operator login**

- Username: `operator`
- Password: stored as the sensitive `OPERATOR_PASSWORD` variable in Vercel. Do not publish it in this public repository; the test password is shared separately with the reviewer.

The deployment uses a Neon pooled PostgreSQL URL. Its schema and initial knowledge articles have been provisioned in Neon. The FastAPI entrypoint is `api/index.py`, routed through the rewrite in `vercel.json`. The Vercel Queues subscriber is declared in `pyproject.toml`.

The Vercel production build is ready. The seeded database was verified. Before testing Helpdesk webhooks, set `HELPDESK_ALLOWED_HOSTS` to the real Helpdesk hostname in Vercel and redeploy. `OPENAI_API_KEY` is optional; without it, the local fallback creates deterministic drafts. Vercel Queues uses deployment OIDC for publish and subscriber delivery; queue processing and external Helpdesk delivery still need a live smoke test.

## Known limitations

- The Vercel queue SDK is beta and its Python APIs may change. Queue publication and consumer delivery need a live Vercel smoke test.
- Demo shared-password auth must be replaced for public use.
- Receiver idempotency support is required to safely retry ambiguous network timeouts.
- A real production smoke test cannot happen before external project setup and deployment.
