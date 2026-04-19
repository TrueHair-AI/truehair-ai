import atexit
import base64
import binascii
import json
import os
import tempfile

from flask import Flask
from flask_migrate import Migrate

from app.models import db
from config import Config

migrate = Migrate()

_creds_path = None


def _setup_gcp_credentials():
    encoded = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not encoded:
        return

    global _creds_path
    if _creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds_path
        return

    try:
        key_json = base64.b64decode(encoded).decode("utf-8")
        json.loads(key_json)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON format"
        ) from exc

    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        f.write(key_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
    _creds_path = path

    def _cleanup():
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    atexit.register(_cleanup)


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
