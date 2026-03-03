import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "super-secret-default-key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///truehair.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    SERVER_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")