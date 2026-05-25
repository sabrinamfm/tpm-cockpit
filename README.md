# TPM Cockpit

Local-first cockpit for Technical Program Managers.

This repository currently contains only the Python/FastAPI foundation:

- FastAPI app
- SQLite database configuration
- SQLAlchemy session setup
- Alembic migrations scaffold
- Health-check endpoint
- Pytest test coverage for the health check

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

## Configuration

Copy `.env.example` to `.env` if you want to override local settings.

By default, the app uses:

```text
sqlite:///./data/cockpit.db
```

The `data/` directory is intentionally ignored by Git and is where the real local SQLite database should live.

## Run the API

```bash
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Migrations

Create a migration after adding SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

## Tests

```bash
pytest
```
