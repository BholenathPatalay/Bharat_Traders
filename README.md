# Nifty 50 Live Option Chain Dashboard

Production-ready monorepo for a FastAPI + React option-chain dashboard with Redis caching, WebSocket deltas, Google OAuth, PostgreSQL-backed watchlist pins, dark/light mode, virtualized rendering, and worker-based range sums.

## Stack

- Backend: Python 3.11+, FastAPI, FastAPI Users, SQLAlchemy async, Redis, PostgreSQL, WebSockets
- Frontend: React + Vite + TypeScript, Tailwind CSS, shadcn-style UI primitives, Zustand, TanStack Table, TanStack Virtual
- Infra: Docker Compose

## Folder Structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- core/
|   |   |-- routers/
|   |   |-- schemas/
|   |   `-- services/
|   |-- Dockerfile
|   `-- pyproject.toml
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- hooks/
|   |   |-- lib/
|   |   |-- store/
|   |   |-- types/
|   |   `-- workers/
|   |-- Dockerfile
|   `-- nginx.conf
|-- docker-compose.yml
`-- .env.example
```

## Quick Start

1. Copy `.env.example` to `.env` and fill in your Dhan and Google OAuth credentials.
2. Register `GOOGLE_OAUTH_REDIRECT_URL` in Google Cloud Console.
3. Run `docker compose up --build`.
4. Open `http://localhost:4173`.

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
# Activate venv:
# - Windows PowerShell: . .\.venv\Scripts\Activate.ps1
# - macOS/Linux:        source .venv/bin/activate
python -m pip install -U pip "setuptools<81"
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Performance Checklist

- [x] Backend: Redis caching enabled
- [x] Frontend: Virtualized list for option chain rows
- [x] Frontend: Web Worker for sum calculations
- [x] Frontend: Debounced window resize listener
- [x] Network: WebSocket auto reconnect on disconnect

## Notes

- The INDstocks payload normalizer is intentionally defensive because option-chain payload shapes vary between providers and integrations.
- Watchlist pins are persisted per authenticated user in PostgreSQL.
- Google OAuth is handled through FastAPI Users and a frontend callback route that exchanges the Google code for a JWT.

### Windows tip (WebSocket `localhost` failures)

If the frontend shows a browser console error like `WebSocket connection to 'ws://localhost:8000/ws/option-chain' failed`, set `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` to use `127.0.0.1` instead of `localhost` (or run the backend bound to IPv6). The default `.env.example` uses `127.0.0.1` for reliability.

### Windows tip (Uvicorn `WinError 10013` on port 8000)

If `uvicorn ... --port 8000` fails with `WinError 10013` ("access permissions"), the port is typically already in use with an exclusive bind. Find and stop the owning process, or run the backend on a different port and update `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` accordingly.

## FYERS (optional data provider)

This backend can use FYERS `options-chain-v3` as an alternative upstream by setting `OPTION_CHAIN_PROVIDER=fyers` and configuring `FYERS_CLIENT_ID`, `FYERS_SECRET_KEY`, and `FYERS_REDIRECT_URI` in your `.env`.

- Start auth: call `GET /api/v1/fyers/auth-url` and open the returned `auth_url` in your browser.
- After login, FYERS redirects to your `FYERS_REDIRECT_URI` with `auth_code` and `state` query params; forward those to `GET /api/v1/fyers/callback?auth_code=...&state=...`.
- The backend stores the resulting access token in Redis (key `fyers:access-token`).
