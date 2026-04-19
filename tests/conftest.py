import uuid
from datetime import datetime, timezone

import pytest

from app import create_app
from app.models import (
    Consent,
    ExperimentSession,
    GeneratedImage,
    Hairstyle,
    Stylist,
    UserImage,
    db,
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    GEMINI_API_KEY = "test-gemini-key"
    R2_ACCOUNT_ID = "test-account-id"
    R2_ACCESS_KEY_ID = "test-access-key"
    R2_SECRET_ACCESS_KEY = "test-secret-key"
    R2_BUCKET_NAME = "test-bucket"


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


def _make_consented_session(app, experiment_group="control"):
    """Create a Consent + ExperimentSession row and return the session_id."""
    sid = str(uuid.uuid4())
    with app.app_context():
        db.session.add(Consent(session_id=sid, experiment_group=experiment_group))
        db.session.add(
            ExperimentSession(
                session_id=sid,
                experiment_group=experiment_group,
                started_at=datetime.now(timezone.utc),
                last_ping_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()
    return sid


@pytest.fixture
def session_id(app):
    """Create a consented session and return the session_id."""
    return _make_consented_session(app)


@pytest.fixture
def auth_client(app, session_id):
    """Test client with a consented session cookie set."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["session_id"] = session_id
    return client


@pytest.fixture
def experimental_client(app):
    """Test client consented into the experimental group."""
    sid = _make_consented_session(app, experiment_group="experimental")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["session_id"] = sid
    return client, sid


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
def user_image(app, session_id):
    with app.app_context():
        ui = UserImage(session_id=session_id, image_url="uploads/test_photo.jpg")
        db.session.add(ui)
        db.session.commit()
        db.session.refresh(ui)
        return ui


@pytest.fixture
def generated_image(app, session_id, user_image, hairstyle):
    with app.app_context():
        gi = GeneratedImage(
            session_id=session_id,
            user_image_id=user_image.id,
            hairstyle_id=hairstyle.id,
            image_url="uploads/gen_test.webp",
        )
        db.session.add(gi)
        db.session.commit()
        db.session.refresh(gi)
        return gi
