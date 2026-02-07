# Ops Automation MVP

Lean ops automation stack for a family office. Ingests inbound requests, creates Todoist tasks, answers SOP questions via RAG, and sends outbound notifications through n8n.

## What It Does
- Inbound intake (Slack/webhook) → AI extracts task fields → Todoist task created.
- SOP Q&A via RAG over pgvector.
- Daily enforcement for high‑priority tasks (reminders if no update).
- Outbound messaging via a single n8n webhook.

## Architecture
```mermaid
graph TD
  Slack[Slack or Webhook] --> n8nInbound[n8n Inbound]
  n8nInbound --> Backend[FastAPI Backend]
  Backend -->|RAG (pgvector)| Postgres[(Postgres + pgvector)]
  Backend -->|Create Task| Todoist[Todoist]
  Backend --> n8nOutbound[n8n Outbound]
  n8nOutbound --> Slack
  Backend -->|RAG call| RagAgent[RAG Agent Service]
```

## Services
- `backend`: FastAPI app (inbound, ask, enforce, debug)
- `rag_agent`: RAG answer service on `:9000`
- `postgres`: pgvector storage
- `n8n`: inbound/outbound orchestrator

## Project Structure
```text
.
├── backend/
│   ├── app/
│   │   ├── data/
│   │   │   └── sops/                # SOP markdown files
│   │   ├── db/                      # Models + init.sql
│   │   ├── routes/                  # API endpoints
│   │   ├── scripts/                 # One-off utilities (ingest)
│   │   └── services/                # Core business logic
│   └── requirements.txt
├── rag_agent/
│   ├── app/                         # RAG service
│   └── requirements.txt
├── n8n/                             # n8n workflows / docs
├── docker-compose.yml
├── .env.example
└── README.md
```

## Setup
1. Copy env file:
   ```bash
   cp .env.example .env
   ```
2. Fill in `.env` (Todoist, OpenAI, outbound webhook).
3. Build + start:
   ```bash
   docker compose up -d --build
   ```

## SOP Ingestion
After DB is up, ingest SOPs into pgvector:
```bash
docker compose exec backend python -m app.scripts.ingest_sops
```

## n8n Notes
- Inbound workflow: Webhook → call backend `/inbound`
- Outbound workflow: Webhook `/ops-outbound` receives JSON and sends to Slack
- Keep `N8N_OUTBOUND_WEBHOOK_URL` in `.env`:
  ```
  N8N_OUTBOUND_WEBHOOK_URL=http://n8n:5678/webhook/ops-outbound
  ```

## Endpoints
- `POST /inbound` – intake message → create task → outbound notification
- `POST /ask` – SOP Q&A (calls `rag_agent`)
- `POST /tasks/enforce` – reminders for due high‑priority tasks
- `GET /debug/db` – DB snapshot (audit, inbox, tasks, enforcement)
- `GET /health` – health check

## Example Usage

### Inbound task creation (via n8n webhook)
```bash
curl -X POST "http://localhost:5678/webhook/chat-message" \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "slack",
    "source_channel": "expenses",
    "source_user": "U_test",
    "sender_user": "chief_of_staff",
    "receiver_user": "U_test",
    "thread_id": "slack:C123:1234567.890",
    "text": "Reserve a flight to Greece for CEO before midday today.",
    "attachments": [],
    "timestamp": "2026-02-06T10:00:00Z"
  }'
```

### SOP Q&A (DM the user)
```bash
curl -s -X POST "http://localhost:8000/ask" \
  -H 'Content-Type: application/json' \
  -d '{"query":"What must be included on invoices for SFO purchases?","user_id":"U_test"}' \
| python3 -m json.tool
```

### Enforce reminders
```bash
curl -X POST "http://localhost:8000/tasks/enforce"
```

### DB snapshot
```bash
curl "http://localhost:8000/debug/db?limit=5" | python3 -m json.tool
```

## Notes
- SOP source files live in `backend/app/data/sops/`.
- RAG is handled by `rag_agent` and called by the backend via `RAG_AGENT_URL`.
- Outbound notifications go through n8n: `N8N_OUTBOUND_WEBHOOK_URL`.
