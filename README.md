Vehicle Designer API

Quick start
- Create and activate a Python 3.12 virtualenv.
- Install deps: `pip install -r requirements.txt`

Environment
- Supabase (required for versions storage):
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- Ark (optional for real generation; fake by default):
  - `ARK_API_KEY` (required to enable real Ark)
  - `ARK_BASE_URL` (optional; defaults to https://ark.cn-beijing.volces.com/api/v3)
  - `ARK_FAKE_MODE` (set `false` to enable real Ark)
- Optional concurrency tuning:
  - `ARK_MAX_WORKERS` (default 4)

Initialize database (Supabase)
- Open Supabase SQL editor for your project
- Paste and run `docs/project/schema.sql`

Run the API
- `uvicorn app.main:app --host 0.0.0.0 --port 8000`

Enable real Ark
- `pip install 'volcengine-python-sdk[ark]'`
- `export ARK_API_KEY=...`
- `export ARK_FAKE_MODE=false`

Endpoints
- See `docs/project/technical_state.md` section "后端 API（FastAPI）" for full contract

