import pytest

from app import create_app
from app.models import GeneratedImage, Hairstyle, Stylist, User, UserImage, db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    GOOGLE_CLIENT_ID = "test-id"
    GOOGLE_CLIENT_SECRET = "test-secret"
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


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(
            email="test@example.com",
            username="testuser",
            first_name="Test",
            last_name="User",
        )
        db.session.add(u)
        db.session.commit()
        db.session.refresh(u)
        return u


@pytest.fixture
def admin_user(app):
    with app.app_context():
        u = User(
            email="admin@example.com",
            username="adminuser",
            first_name="Admin",
            last_name="User",
            is_admin=True,
        )
        db.session.add(u)
        db.session.commit()
        db.session.refresh(u)
        return u


@pytest.fixture
def auth_client(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
    return client


@pytest.fixture
def admin_client(client, admin_user):
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user.id
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
def user_image(app, user):
    with app.app_context():
        ui = UserImage(user_id=user.id, image_url="uploads/test_photo.jpg")
        db.session.add(ui)
        db.session.commit()
        db.session.refresh(ui)
        return ui


@pytest.fixture
def generated_image(app, user, user_image, hairstyle):
    with app.app_context():
        gi = GeneratedImage(
            user_id=user.id,
            user_image_id=user_image.id,
            hairstyle_id=hairstyle.id,
            image_url="uploads/gen_test.webp",
        )
        db.session.add(gi)
        db.session.commit()
        db.session.refresh(gi)
        return gi
