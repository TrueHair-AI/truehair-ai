from flask import Flask
from flask_migrate import Migrate

from app.models import db
from config import Config

migrate = Migrate()


def create_app(config_class=Config):
    """Create and configure the Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.main import main_bp

    app.register_blueprint(main_bp)

    return app
