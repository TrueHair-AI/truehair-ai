from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask_migrate import Migrate

from app.models import db
from config import Config

oauth = OAuth()
migrate = Migrate()


def create_app(config_class=Config):
    """Create and configure the Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    oauth.init_app(app)
    migrate.init_app(app, db)

    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config["SERVER_METADATA_URL"],
        client_kwargs={"scope": "openid email profile"},
    )

    from app.routes.auth import auth_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
