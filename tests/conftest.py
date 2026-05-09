import secrets
import uuid

import pytest

from app import create_app
from app.models import (
    GeneratedImage,
    Hairstyle,
    Stylist,
    User,
    db,
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    GOOGLE_CLOUD_PROJECT = "test-project"
    GOOGLE_CLOUD_LOCATION = "us-central1"
    ADMIN_EMAILS = "admin@example.com,other-admin@example.com"
    GOOGLE_OAUTH_CLIENT_ID = "test-client-id"
    GOOGLE_OAUTH_CLIENT_SECRET = "test-client-secret"


@pytest.fixture
def app():
    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user(app, email="user@example.com", is_admin=False):
    """Create a User row and return its id."""
    with app.app_context():
        u = User(
            google_sub=f"test-{secrets.token_hex(8)}",
            email=email,
            display_name=email.split("@")[0].title(),
            is_admin=is_admin,
            storage_salt=secrets.token_hex(32),
        )
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def session_id():
    """Mint a session_id (the per-browser UUID) without persisting anything."""
    return str(uuid.uuid4())


@pytest.fixture
def auth_client(app, session_id):
    """Test client signed in as a non-admin user.

    Sets both `user_id` (for login_required) and `session_id` (the per-browser
    UUID that GeneratedImage / Rating / Recommendation rows are scoped to).
    """
    user_id = _make_user(app, email="user@example.com")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["session_id"] = session_id
    return client


@pytest.fixture
def admin_client(app):
    """Test client signed in as an admin user (User.is_admin=True)."""
    user_id = _make_user(app, email="admin@example.com", is_admin=True)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return client


@pytest.fixture
def hairstyle(app):
    with app.app_context():
        h = Hairstyle(
            name="Test Cut",
            description="A test style",
            category="MODERN",
            image_url="/static/test.png",
        )
        db.session.add(h)
        db.session.commit()
        db.session.refresh(h)
        return h


@pytest.fixture
def stylist(app):
    with app.app_context():
        s = Stylist(
            name="Jane Stylist",
            specialties="Cuts, Color",
            email="jane@salon.com",
        )
        db.session.add(s)
        db.session.commit()
        db.session.refresh(s)
        return s


@pytest.fixture
def generated_image(app, session_id, hairstyle):
    with app.app_context():
        gi = GeneratedImage(
            session_id=session_id,
            hairstyle_id=hairstyle.id,
        )
        db.session.add(gi)
        db.session.commit()
        db.session.refresh(gi)
        return gi
