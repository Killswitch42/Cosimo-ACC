# Medici Analytica Accounting

FastAPI + PostgreSQL accounting backend for Medici Analytica.

The project currently includes:

- Phase 01: company, fiscal period, Czech chart of accounts, health endpoint
- Phase 02: immutable ledger journal entries, reversals, account balances, CNB FX rates
- Phase 03: invoice posting, DUZP validation, VAT register, kontrolní hlášení sections

## Local Setup

Use these commands from the project root:

```bash
cd ~/Documents/Projects/Cosimo\ Acc/Cosimo\ Accounting/CosimoApp/medici-analytica
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `python3` is Python 3.14 on your machine, this is OK with the current dependency pins. If you later install Python 3.11, you can recreate the venv with `python3.11 -m venv .venv`.

## Start PostgreSQL Without Compose

This machine does not currently have the Docker Compose plugin installed, so use plain Docker:

```bash
docker network create medici-phase01-net 2>/dev/null || true

docker rm -f medici-phase01-db 2>/dev/null || true
docker run -d \
  --name medici-phase01-db \
  --network medici-phase01-net \
  -e POSTGRES_USER=medici \
  -e POSTGRES_PASSWORD=medici_dev_pass \
  -e POSTGRES_DB=medici_accounting \
  -p 5432:5432 \
  --health-cmd="pg_isready -U medici -d medici_accounting" \
  --health-interval=5s \
  --health-timeout=5s \
  --health-retries=5 \
  postgres:15-alpine
```

Wait until the database is healthy:

```bash
docker ps --filter name=medici-phase01-db
```

## Migrate and Seed

For commands run on the host, `.env` uses `localhost:5432`.

```bash
source .venv/bin/activate
alembic upgrade head
python -m app.seed.run_seed
```

Rollback to an empty database:

```bash
alembic downgrade base
```

## Run the App on the Host

Port `8000` can only be used by one process/container at a time. If an old app container is already running, stop it first:

```bash
docker rm -f medici-phase01-app 2>/dev/null || true
```

Then start FastAPI:

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Expected shape:

```json
{"status":"healthy","service":"Medici Analytica Accounting","phase":"01","ledger_accounts_loaded":299}
```

## Run the App in Docker

Build the image:

```bash
docker build -t medici-phase01-app .
```

Run it on the same Docker network as PostgreSQL:

```bash
docker rm -f medici-phase01-app 2>/dev/null || true
docker run -d \
  --name medici-phase01-app \
  --network medici-phase01-net \
  --env-file .env \
  -e DATABASE_URL=postgresql+asyncpg://medici:medici_dev_pass@medici-phase01-db:5432/medici_accounting \
  -p 8000:8000 \
  medici-phase01-app \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Run Tests

PostgreSQL must be running, migrations must be applied, and seed data must be loaded.

```bash
source .venv/bin/activate
pytest tests/ -v
```

Or run tests inside the Docker image:

```bash
docker run --rm \
  --network medici-phase01-net \
  --env-file .env \
  -e DATABASE_URL=postgresql+asyncpg://medici:medici_dev_pass@medici-phase01-db:5432/medici_accounting \
  medici-phase01-app \
  pytest tests/ -v
```

## Common Errors

### `pg_config executable not found`

This happened because the old dependency pins did not provide a wheel for the local Python version, so `pip` tried to compile `psycopg2-binary` from source. The requirements now use newer compatible pins. Reinstall with:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'pydantic'`

Dependencies did not finish installing. Re-run:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Also make sure you are using the venv executables:

```bash
which python
which alembic
```

Both should point inside `.venv`.

### `docker: unknown command: docker compose`

Docker is installed, but the Compose plugin is not. Use the plain `docker run` commands in this README.

### `ERROR: [Errno 98] Address already in use`

Something is already listening on port `8000`, usually the app container:

```bash
docker ps --filter name=medici-phase01-app
docker rm -f medici-phase01-app
```

Then run `uvicorn` again.
