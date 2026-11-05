# RenewOps – Subscription & Contract Management Platform

A production-quality MVP subscription and contract management platform for startups and growing businesses, featuring rule-based renewal risk scoring, multi-currency spending analytics, and full **Remote Model Context Protocol (MCP)** integration for Claude.

---

## 1. System Architecture (Option A: Unified Deployment)

```
                            Public HTTPS Endpoint
                                     │
                             FastAPI Application
                                     │
                 ┌───────────────────┴───────────────────┐
                 │                                       │
            REST API Layer                           Remote MCP
           (/api/v1/...)                               (/mcp)
                 │                                       │
                 ├───────────────────┬───────────────────┤
                 ▼                   ▼                   ▼
        Subscription Service   Renewal Service   Analytics Service
                 │                   │                   │
                 └───────────────────┼───────────────────┘
                                     │
                            PostgreSQL / SQLite
                                     │
                         Web Dashboard Frontend
```

- **Unified Runner**: A single deployed container or process on port `8000` hosts the REST API, the Web Dashboard UI, and the Streamable HTTP MCP server (`/mcp`).
- **Zero Duplication**: Claude and human users interact with the exact same business logic services and database.
- **Tenant Isolation**: All operations are strictly bounded to the authorized organization (`DEMO_ORG_ID`).
- **No AI APIs inside Application**: 100% pure Python business logic and rule-based calculations; Claude interacts solely via the official MCP protocol.

---

## 2. Quick Start (Local Setup)

### Prerequisites
- Python 3.12+
- (Optional) Docker for PostgreSQL

### Step 1: Install Dependencies
```powershell
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
```

### Step 2: Environment Configuration
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
For instant local testing without Docker, `.env` defaults to SQLite:
```ini
DATABASE_URL=sqlite:///./renewops.db
```
For PostgreSQL (Docker):
```ini
DATABASE_URL=postgresql+psycopg2://renewops:renewops@localhost:5432/renewops
```
*(Start PostgreSQL container with: `docker compose up -d`)*

### Step 3: Seed Realistic Demo Data
```powershell
.\venv\Scripts\python.exe scripts\seed_demo_data.py
```

### Step 4: Start the Unified Application
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload
```
Open in browser:
- **Dashboard UI**: [http://localhost:8000](http://localhost:8000)
- **Subscriptions**: [http://localhost:8000/subscriptions.html](http://localhost:8000/subscriptions.html)
- **Upcoming Renewals**: [http://localhost:8000/renewals.html](http://localhost:8000/renewals.html)
- **Renewal Risk Breakdown**: [http://localhost:8000/risk.html](http://localhost:8000/risk.html)
- **Spending Analytics (MRR/ARR)**: [http://localhost:8000/analytics.html](http://localhost:8000/analytics.html)
- **Swagger REST API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Remote MCP Endpoint**: [http://localhost:8000/mcp](http://localhost:8000/mcp)

---

## 3. Remote MCP Integration (Claude)

RenewOps implements the official Python MCP SDK with Streamable HTTP transport.

### 6 Exposed MCP Tools:
1. `create_subscription`: Create a new subscription record with automatic risk evaluation.
2. `list_subscriptions`: Filter subscriptions by status, department, or keyword.
3. `get_subscription`: Retrieve full subscription details and risk reasons.
4. `update_subscription`: Update subscription metadata, renewal date, or decision.
5. `get_upcoming_renewals`: Query subscriptions renewing in the next N days.
6. `get_spending_summary`: Retrieve active MRR, ARR, and department rollups.

### Connecting Claude Custom Connector (Remote URL)
When deployed or exposed via tunnel (`ngrok http 8000`):
- **Connector URL**: `https://<your-domain>/mcp`
- **Optional Header** (if `MCP_API_KEY` is configured):
  `Authorization: Bearer <MCP_API_KEY>`

### Connecting Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "renewops": {
      "command": "d:\\College\\RenewOps\\venv\\Scripts\\python.exe",
      "args": ["-m", "mcp.client.sse", "http://localhost:8000/mcp"]
    }
  }
}
```

---

## 4. Automated Testing & Verification

Run the complete test suite:
```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Execute the 7-step bidirectional workflow verification script:
```powershell
.\venv\Scripts\python.exe scripts\test_mcp_flow.py
```
This tests:
1. User prompt to Claude ("Add AWS subscription...")
2. Claude calls MCP `create_subscription`
3. Record verified in PostgreSQL / ORM
4. Dashboard and REST API immediately reflect the record
5. Claude queries upcoming renewals via MCP
6. Claude updates renewal decision to "Renew" (Audit trail verified)
7. User edits on Dashboard → Claude retrieves the updated data via MCP.

---

## 5. Security & Multi-Currency Architecture

- **HTTP Middleware-Level Auth**: Authentication is verified at the HTTP transport boundary (`/mcp`), ensuring Claude's tool arguments remain clean and domain-focused.
- **Tenant Isolation**: Every database interaction is scoped to the organization (`DEMO_ORG_ID`).
- **REST Write Protection**: Configurable `ADMIN_API_KEY` protects mutations on public deployments.
- **Multi-Currency Separation**:
  - Primary MRR/ARR and department rollups are strictly calculated from **INR subscriptions**.
  - Non-INR subscriptions (USD, EUR, GBP) are isolated in a separate breakdown and never blindly summed without conversion.
- **Configurable Risk Rules**: Risk cost thresholds (e.g., ₹50k/₹100k INR, $600/$1,200 USD) represent configurable budget guardrails and governance policies rather than static market assumptions.

