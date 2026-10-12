# Campus Customs — Agentic Back Office

A small campus merchandise shop's back-office desk, run by a team of five PydanticAI agents
(Boss, Inventory, Accounting, Facilities, Customer Service) that read and write shop data only
through an MCP server, fronted by a FastAPI backend and a React dashboard. Every agent uses a
single model, `gpt-6-luna`, through Portkey.

See `output/harness.md` for the full technical reference (database schema, every MCP tool, every
agent's role, every API route, the dashboard, and the safety rules enforced in code) and
`output/design.md` for the dashboard's visual design rationale. `AI_prompts.md` is the full log
of every prompt used to build this project, problem by problem.

## Project layout

```
.
├── data/                  campus_customs.db (original, never modified) and
│                          campus_customs_new.db (the working copy every tool reads/writes)
├── mcp_server/            the MCP server (server.py) - the only thing that ever touches the db
├── backend/               FastAPI app (main.py) + the 5 PydanticAI agents + their prompts
├── frontend/              React + Vite + TypeScript dashboard
└── output/                generated artifacts: harness.md, design.md, the planning/results
                           pages, the audit trail, and this run's screenshots
```

## One-time setup

**1. Python environment** (from this folder):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. Node dependencies**:

```powershell
cd frontend
npm install
cd ..
```

**3. Portkey API key**:

```powershell
copy .env.example .env
```

Then open `.env` and set `PORTKEY_API_KEY` to your real key. `.env` is gitignored - it is never
committed. Every agent uses exactly one model, `gpt-6-luna`, configured in the single shared
`backend/model.py`; nothing else in the project builds a model or should ever name a different
one.

## Getting a clean working database

Every MCP tool reads and writes `data/campus_customs_new.db` only - `data/campus_customs.db` is
the untouched original and is never opened by any tool. Before a full three-ticket run (or any
time you want to start over), reset the working copy from the original:

- **From the dashboard**: click "Reset data" (confirms before resetting).
- **From the API directly**: `POST http://localhost:8000/reset`.

Resetting also clears the dashboard's in-memory live-events feed, but never touches
`output/audit_trail.json`, which is append-only and keeps every run's history.

## Running everything

Three things run independently; start them in this order.

**1. The MCP server** - normally started automatically (as a subprocess) by whatever connects to
it: Claude Code via the project's `.mcp.json`, or the FastAPI backend via
`backend/mcp_client.py`. You don't need to start it by hand. To run it standalone for a quick
check:

```powershell
.\.venv\Scripts\python.exe -m mcp_server.server
```

**2. The FastAPI backend** (from `backend/`):

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

This also starts the MCP server as a subprocess automatically. Leave this running.

**3. The React dashboard** (from `frontend/`, in a separate terminal):

```powershell
cd frontend
npm run dev
```

Open the URL it prints (`http://localhost:5173`). The dashboard talks to the backend at
`http://localhost:8000` - CORS is already open for local development.

## Doing a full three-ticket run

1. Reset the database (see above) so all three tickets start `open` and cash starts at $3,400.
2. From the dashboard, click "Start agent team" on a ticket, watch the live activity feed, and
   approve any payment proposals that come up (they need a human - no agent can approve its own
   proposal).
3. Repeat for the other two tickets.

## Secrets

- The only secret this project uses is `PORTKEY_API_KEY`, read once from `.env` by
  `backend/model.py` and never printed or logged anywhere.
- `.gitignore` excludes `.env`, `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, and anything
  matching `*.key` or `*token*`.
- `.env.example` has a placeholder only - never a real key.
