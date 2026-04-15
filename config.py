import os

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
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    SERVER_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
