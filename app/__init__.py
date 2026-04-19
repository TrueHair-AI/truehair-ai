import base64
import json
import os
import tempfile

from flask import Flask
from flask_migrate import Migrate

from app.models import db
from config import Config

migrate = Migrate()


def _setup_gcp_credentials():
    encoded = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not encoded:
        return

    try:
        key_json = base64.b64decode(encoded).decode("utf-8")
        json.loads(key_json)
    except Exception:
        raise RuntimeError("Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON format")

    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(key_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path


def create_app(config_class=Config):
    """Create and configure the Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    _setup_gcp_credentials()

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.main import main_bp

    app.register_blueprint(main_bp)

    return app
