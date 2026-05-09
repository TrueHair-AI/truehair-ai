<div align="center">

<img src="app/static/images/truehair-logo.png" alt="TrueHair AI logo" width="200">

# TrueHair AI

**See yourself in any hairstyle, instantly.**

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-3.1-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![SQLite](https://img.shields.io/badge/SQLite-dev-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-prod-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Vertex AI](https://img.shields.io/badge/Vertex%20AI-Gemini-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![JavaScript](https://img.shields.io/badge/JavaScript-vanilla-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![Heroku](https://img.shields.io/badge/Heroku-deploy-430098?style=for-the-badge&logo=heroku&logoColor=white)](https://www.heroku.com/)
[![Ruff](https://img.shields.io/badge/Ruff-lint-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)

</div>

---

TrueHair AI is a web app that lets you preview hairstyles on your own photo before you commit. Upload a selfie, pick a style from the catalog (or describe your own), and TrueHair generates a realistic visualization powered by Google's Gemini image model on Vertex AI. From there you can save styles to a private gallery and connect with local stylists to book the look.

The platform runs on Vertex AI in **Zero Data Retention (ZDR)** mode — Google does not retain your photos or prompts, and TrueHair only stores results you explicitly save to your gallery.

## Local development

### Prerequisites

- Python **3.14** (the project pins to `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) for dependency and venv management
- A Google Cloud project with Vertex AI enabled, plus a service-account key
- Google OAuth 2.0 credentials (Client ID + secret) for sign-in

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Create a `.env` file at the repo root:

```bash
# Flask
FLASK_SECRET_KEY=change-me-to-a-long-random-string
DATABASE_URL=sqlite:///truehair.db          # leave unset for the default

# Google OAuth (sign-in)
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-client-secret

# Vertex AI (image generation)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'   # full JSON key, on one line

# Admin seeding (comma-separated emails granted is_admin=True on first migration)
ADMIN_EMAILS=you@example.com

# Cloudflare R2 (optional — used for stylist portfolio assets)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
```

> `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` come from the Google Cloud Console → APIs & Services → Credentials. Add `http://localhost:5000/login/google/authorized` to the authorized redirect URIs.

### 3. Initialize the database and seed catalogs

```bash
uv run flask db upgrade
uv run python seed_hairstyles.py
uv run python seed_stylists.py
```

### 4. Run the dev server

```bash
uv run flask run
```

The app is now live at http://localhost:5000.

### Tests and lint

```bash
uv run pytest          # full test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```

## Architecture

| Layer | Tech |
|---|---|
| Web framework | Flask 3 + Jinja templates |
| ORM / migrations | SQLAlchemy + Flask-Migrate (Alembic) |
| Database | SQLite (local dev) · PostgreSQL (production) |
| Auth | Google OAuth via `flask-dance` |
| AI | Google Gemini on Vertex AI (ZDR mode) — see [`get_genai_client()` in app/routes/main.py](app/routes/main.py) |
| Frontend | Bootstrap 5, vanilla JavaScript |
| Client storage | IndexedDB-backed gallery — generated images are stored on-device until the user explicitly saves them server-side |
| Object storage | Cloudflare R2 (stylist portfolio assets) |
| Server runtime | Gunicorn (1 worker × 8 threads, `gthread` worker class) |

The Vertex AI client is constructed once via `get_genai_client()`. **Do not** swap it for the Gemini Developer API constructor — Vertex mode is what gives the app its ZDR guarantee.

## Deployment

The app deploys to Heroku via the [`Procfile`](Procfile):

- **`web`** — `gunicorn run:app --timeout 120 --workers 1 --threads 8 --worker-class gthread …`
- **`release`** — `flask db upgrade && python seed_hairstyles.py && python seed_stylists.py`

Set the same environment variables listed above on the Heroku app, plus a managed Postgres add-on for `DATABASE_URL`.

## Contributing

1. Branch off `main` with a descriptive prefix — `feat/…`, `fix/…`, `docs/…`, `refactor/…`.
2. Run `uv run pytest` and `uv run ruff check .` before pushing.
3. Open a pull request using the [PR template](.github/pull_request_template.md). For new bugs or feature ideas, file an issue first using the [issue templates](.github/ISSUE_TEMPLATE).
4. Keep commit messages in [Conventional Commits](https://www.conventionalcommits.org/) style (e.g. `feat(gallery): add fullscreen viewer`).

## Project history

TrueHair began as an IRB-supervised research study at Colby College. Compliance notes from that phase — specifically the IP-stripping logging posture — are preserved in [docs/irb-archive.md](docs/irb-archive.md) for future reference.
