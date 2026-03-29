# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

TrueHair AI is a Flask web application for AI-powered hairstyle visualization. It uses Python 3.14, Flask, SQLAlchemy, Google OAuth, Google Gemini AI, and Cloudflare R2 for storage.

### Package manager

This project uses **uv** with a `uv.lock` lockfile. Always use `uv run` to execute Python commands (e.g. `uv run pytest`, `uv run ruff check .`, `uv run python run.py`).

### Running the dev server

```
uv run python run.py
```

Starts Flask on **port 8000** with debug mode. Uses SQLite (`truehair.db`) by default when `DATABASE_URL` is not set — no Postgres needed for local dev.

### Seeding the database

Before running the app for the first time, seed hairstyles and stylists:

```
uv run python seed_hairstyles.py
uv run python seed_stylists.py
```

These are idempotent — safe to re-run.

### Linting

```
uv run ruff check .
```

### Testing

```
uv run pytest -v
```

All tests use an in-memory SQLite database and mock external services (R2, Gemini, OAuth). No API keys or external services are needed for tests.

### Environment variables

See `.env.example` for the full list. For local development without external services, the app starts fine without any `.env` file (uses SQLite and default secret key). Google OAuth, Gemini API, and R2 storage require their respective keys to be set for those features to work.

### Gotchas

- Python 3.14+ is required (`requires-python = ">=3.14"` in `pyproject.toml`). The `uv sync` command handles installing the correct Python version automatically.
- The app auto-creates database tables on startup via `db.create_all()` in the app factory — no migration tool is used.
