import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class for the Flask application."""

    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "super-secret-default-key")
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or "sqlite:///truehair.db"
    ).replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_SCHEMA = True
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    # Anonymous session cookie (IRB-compliant identity; see app/services/session_identity.py)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")

    # Admin dashboard OAuth gate (issue #63). Operational auth only — not part
    # of the study protocol; participants never see this flow.
    ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "")
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
