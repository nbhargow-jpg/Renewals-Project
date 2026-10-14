# Mobileum Horizon

> Internal web app that replaces the daily PowerPoint for the renewals pipeline.

---

## Quick Start (Windows)

```powershell
# One command — installs everything, seeds DB, starts both servers
.\start.ps1
```

Then open **http://localhost:5173** in your browser.

---

## Manual Start (two terminals)

**Terminal 1 — Backend**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
python -m backend.seed          # first run only
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```powershell
cd frontend
npm install
npm run dev
```

**Troubleshooting: Port already in use**
If you get `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`, it means an older uvicorn backend is still running. You can kill it in PowerShell with:
```powershell
Get-NetTCPConnection -LocalPort 8000 | Stop-Process
```

---

## Run Tests

```powershell
.venv\Scripts\activate
pytest backend/tests/ -v
```

Tests assert the Oct 5 reference numbers (ACV $120.51M, 3,086 rows, all approval counts, all forecast category counts) computed from the real Excel files.

---

## AI Configuration

By default, AI runs in **demo mode** (`DEMO_MODE=true` or when no API key is set) — no API key required, answering directly and deterministically from aggregated analytics tools and database benchmarks.

### External LLM Configuration (OpenAI-compatible)

To connect a company-approved OpenAI-compatible LLM endpoint, set the following in `.env`:

```env
DEMO_MODE=false
LLM_BASE_URL=https://api.openai.com/v1     # OpenAI-compatible completions endpoint
LLM_API_KEY=your_api_key_here             # Server-side only, never exposed to client
LLM_MODEL=gpt-4o-mini                    # Model name
LLM_TIMEOUT=30                           # Request timeout in seconds
LLM_MAX_TOOL_CALLS=6                     # Maximum tool execution iterations
LLM_SEND_MODE=aggregates                 # "aggregates" (default) | "full"
```

#### Privacy & Security Architecture (`LLM_SEND_MODE`)
- **`aggregates` (Default & Recommended)**: In this mode, only high-level summary figures, calculated totals, and top-5 opportunity snippets are sent to the external LLM endpoint. Raw opportunity rows, account lists, and sensitive deal details are stripped before transmitting tool responses.
- **`full`**: Sends complete tool outputs to the model. Use only with enterprise private-tenant endpoints approved for confidential commercial data.
- **Untrusted Data Boundary**: Tool outputs (opportunity names, account names) are treated as untrusted text to prevent prompt injection.
- **Read-Only Whitelist**: The LLM has zero SQL, shell, or filesystem access and can only invoke read-only functions with strict argument whitelisting.

---

## Folder Structure

```
Renewal_Data/
├── start.ps1               # one-command startup (Windows)
├── .env.example            # copy to .env
├── backend/
│   ├── main.py             # FastAPI entrypoint
│   ├── config.py           # all config from .env
│   ├── database.py         # SQLAlchemy sync engine
│   ├── models/             # ORM models (snapshot, opportunity, change_log, daily_summary)
│   ├── services/           # business logic (ingest, analytics, diff, ai, opportunities)
│   ├── routers/            # thin FastAPI routers
│   ├── utils/              # excel_parser, normalise
│   ├── seed.py             # loads real Excel files on first run
│   ├── requirements.txt
│   └── tests/              # pytest with Oct-5 reference assertions
├── frontend/
│   ├── src/
│   │   ├── pages/          # Dashboard, Pipeline, Opportunities, History, AI, Upload, Executive
│   │   ├── components/     # Shell, Sidebar, Topbar, CommandPalette, charts, ui
│   │   ├── design/tokens.ts
│   │   ├── store/appStore.ts
│   │   └── api/client.ts
│   └── package.json
├── data/
│   ├── Renewals Summary 3.xlsx
│   └── Renewal Comparison Tool 11.xlsx
└── assets/
    └── logo.png
```

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+K` / `⌘K` | Open command palette |
| `Ctrl+/` / `⌘/` | Toggle Data Assistant docked panel |
| `↑ ↓` | Navigate palette |
| `Enter` | Open selected page |
| `Esc` | Close palette or docked assistant |

---

## Architecture Notes

- **Immutable snapshots**: Every upload creates a new dated snapshot. Nothing is ever overwritten.
- **Service layer**: All business logic lives in `services/` and accepts `UserContext` — drop in auth/RBAC later without touching routers.
- **AI privacy**: Only aggregated numbers (total ACV, category counts) are sent to external AI providers — never raw rows.
- **Predictive insights**: Rule-based risk scoring with human-readable "why" factors. No fake ML. Shows "collecting history" until 7+ snapshots exist.
- **Executive View**: Uses browser `window.print()` with `@media print` CSS — no server-side PDF generation.
