# Live Multi-Trader FYERS P&L (Local Only)

Local-first app to track multiple FYERS accounts, compute live/unrealized + realized + total P&L, and show a combined dashboard.

## Stack
- Backend: FastAPI
- Ingestion: Python threads + FYERS REST + FYERS data websocket
- Storage: SQLite (local file)
- UI: Streamlit

## Features
- Multi-trader support (2 preconfigured, extensible)
- Fetch positions and trades per trader
- Live LTP updates via websocket (fallback polling every `POLLING_INTERVAL_SEC`)
- P&L metrics:
  - Current (unrealized)
  - Realized (lifetime)
  - Day Realized (today-only by trade timestamp)
  - Total
- Aggregated response across traders
- Fault tolerance:
  - Retry + backoff for API failures
  - Socket reconnect enabled
  - Last known LTP fallback

## Project Layout
- `app/api/main.py` - FastAPI endpoints (`/health`, `/pnl`, `/positions`)
- `app/services/ingestion.py` - polling loop + websocket subscription + live recompute
- `app/services/pnl_engine.py` - P&L formulas
- `app/fyers/client.py` - FYERS SDK wrappers
- `app/db/*` - SQLite schema + repository
- `app/ui/streamlit_app.py` - Streamlit dashboard
- `app/ui/streamlit_compact.py` - compact monitor dashboard
- `app/scripts/set_token.py` - encrypted token setter
- `app/scripts/fyers_auth.py` - FYERS auth-code login automation
- `fyers_auth.py` - shortcut launcher for auth flow

## Setup
1. Create virtual env and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
```

3. Configure traders:
```bash
cp config/traders.example.json config/traders.json
```
Edit `config/traders.json` with FYERS `client_id`, `secret_key`, and `redirect_uri`.
`redirect_uri` must exactly match the value configured in your FYERS app dashboard.

Field mapping from FYERS portal:
- `client_id` = FYERS `APP ID`
- `secret_key` = FYERS `Secret ID`
- `api_key` can be kept same as `client_id` (kept for internal record compatibility)

4. Store encrypted access tokens:
```bash
python fyers_auth.py --alias trader1
python fyers_auth.py --alias trader2
```

Manual fallback (if your redirect URI is not localhost):
```bash
python fyers_auth.py --alias trader1 --manual
```

If your FYERS redirect URI is `https://127.0.0.1`, use manual mode.
Auto callback capture in this app only supports `http://127.0.0.1:<port>/...` or `http://localhost:<port>/...`.

Legacy direct setter (if you already have tokens):
```bash
python -m app.scripts.set_token trader1
python -m app.scripts.set_token trader2
```

## Run
Terminal 1 (backend):
```bash
source .venv/bin/activate
API_PORT=8010 python -m app.main
```

Enable debug raw endpoint when needed:
```bash
DEBUG_RAW_ENABLED=true API_PORT=8010 python -m app.main
```

Terminal 2 (UI):
```bash
source .venv/bin/activate
API_BASE_URL=http://127.0.0.1:8010 streamlit run app/ui/streamlit_app.py --server.port 8502
```

Terminal 3 (optional compact monitor):
```bash
source .venv/bin/activate
API_BASE_URL=http://127.0.0.1:8010 streamlit run app/ui/streamlit_compact.py --server.port 8503
```

## API
### `GET /health`
```json
{"status":"ok"}
```

### `GET /pnl`
```json
{
  "traders": [
    {
      "id": 1,
      "name": "Trader 1",
      "current_pnl": 1200.0,
      "realized_pnl": 500.0,
      "day_realized_pnl": 320.0,
      "total_pnl": 1700.0
    }
  ],
  "combined": {
    "current_pnl": 2000.0,
    "realized_pnl": 800.0,
    "day_realized_pnl": 420.0,
    "total_pnl": 2800.0
  }
}
```

### `GET /positions`
Returns open positions with trader, qty, avg price, LTP, side, and current P&L.

### `GET /debug/raw` (dev-only)
- Disabled by default.
- Enable with `DEBUG_RAW_ENABLED=true`.
- Returns latest raw FYERS responses and normalized payloads per trader.
- Includes `last_attempt_epoch`, `last_refresh_epoch`, and `last_error` for troubleshooting.

## Notes
- No cloud storage is used; data and tokens remain local.
- Access token is stored encrypted; refresh token is also stored if FYERS returns it.
- `traders.access_token` in SQLite is masked by design.
- Realized P&L is derived from tradebook buy/sell aggregation (broker charges excluded).
- If `/debug/raw` shows FYERS `code: -16` (`Could not authenticate the user`), refresh token using `python fyers_auth.py --alias <alias>`.
