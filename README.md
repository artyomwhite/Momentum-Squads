# Momentum Support Desk

AI-assisted support triage for a fictional project analytics SaaS. The service stores helpdesk webhooks idempotently, queues work in PostgreSQL, creates an evidence-based draft, and waits for an operator before sending anything.

## Architecture

\`\`\`mermaid
flowchart LR
  H[Helpdesk webhook] -->|event and job transaction| DB[(PostgreSQL)]
  DB --> W[Worker: lease and SKIP LOCKED]
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

The local compose stack uses a long-running worker. Vercel Functions are request-scoped, not a persistent Python worker. The current Vercel Python runtime supports FastAPI. Vercel Queues provides push consumers, at-least-once delivery and retries; its Python SDK is currently beta. Vercel Hobby Cron runs only once per day, so Cron cannot provide near-real-time processing. Production requires a managed queue subscription and Neon PostgreSQL, with durable database state retained for idempotency and recovery. Queue/account/resource setup must be validated before deployment; this repository does not represent the local worker as deployed on Vercel.

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

Vercel supports FastAPI on its Python runtime. Use a Neon pooled PostgreSQL URL and apply Alembic migrations as a release step. The FastAPI entrypoint is declared in pyproject.toml and its function duration in vercel.json. Run both alembic upgrade head and python -m app.seed against Neon before serving production traffic. Production queue execution still requires a configured Vercel Queues (beta) consumer or another managed queue adapter; queue credentials, a Neon resource, Vercel project setup, production secrets, GitHub push and deployment need account authorization and have not been performed.

After authorization, configure DATABASE_URL, OPERATOR_USERNAME, OPERATOR_PASSWORD, SESSION_SECRET, OPENAI_API_KEY and queue settings as Vercel secrets. Restrict production Helpdesk hosts. Verify webhook, operator authentication, queue consumer, delivery and health endpoints after deployment.

## Known limitations

- Vercel Queues' Python SDK is beta and its current APIs may change.
- The local worker is not a Vercel worker; production queue subscriber configuration remains.
- Demo shared-password auth must be replaced for public use.
- Receiver idempotency support is required to safely retry ambiguous network timeouts.
- A real production smoke test cannot happen before external project setup and deployment.
