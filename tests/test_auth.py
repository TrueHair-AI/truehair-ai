"""Tests for auth routes."""

from unittest.mock import MagicMock, patch


def test_login_unauthenticated(client):
    """Login page renders when not in session."""
    response = client.get("/")
    assert response.status_code == 200


def test_login_authenticated_redirects_to_style_studio(auth_client):
    """When user is in session, / redirects to style-studio."""
    response = auth_client.get("/")
    assert response.status_code == 302
    assert "style-studio" in response.location


def test_logout(auth_client):
    """Logout clears session and redirects to login."""
    response = auth_client.get("/logout")
    assert response.status_code == 302
    assert response.location.endswith("/")
    # Next request should see login page
    r2 = auth_client.get("/")
    assert r2.status_code == 200


@patch("app.oauth")
def test_google_login_redirects(mock_oauth, client, app):
    """Google login redirects to Google OAuth."""
    from flask import redirect

    mock_google = MagicMock()
    with app.test_request_context():
        mock_google.authorize_redirect.return_value = redirect(
            "https://accounts.google.com/"
        )
    mock_oauth.google = mock_google
    response = client.get("/login/google")
    assert mock_google.authorize_redirect.called
    assert response.status_code == 302
    assert "accounts.google.com" in response.location


@patch("app.oauth")
def test_auth_google_no_userinfo_returns_400(mock_oauth, client):
    """auth/google returns 400 when userinfo is missing."""
    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {}
    mock_oauth.google = mock_google
    response = client.get("/auth/google")
    assert response.status_code == 400
    assert b"Failed to fetch user info" in response.data


@patch("app.oauth")
def test_auth_google_new_user_created(mock_oauth, client, app):
    """auth/google creates a new user when email not in DB."""
    from app.models import User

    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {
        "userinfo": {
            "email": "newuser@example.com",
            "given_name": "New",
            "family_name": "User",
            "picture": "https://example.com/photo.jpg",
        }
    }
    mock_oauth.google = mock_google
    with app.app_context():
        assert User.query.filter_by(email="newuser@example.com").first() is None
    response = client.get("/auth/google")
    assert response.status_code == 302
    assert "style-studio" in response.location
    with app.app_context():
        u = User.query.filter_by(email="newuser@example.com").first()
        assert u is not None
        assert u.username == "newuser"
        assert u.first_name == "New"
        assert u.last_name == "User"


@patch("app.oauth")
def test_auth_google_existing_user_logged_in(mock_oauth, client, app, user):
    """auth/google logs in existing user by email."""
    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {
        "userinfo": {
            "email": user.email,
            "given_name": "Test",
            "family_name": "User",
        }
    }
    mock_oauth.google = mock_google
    response = client.get("/auth/google")
    assert response.status_code == 302
    assert "style-studio" in response.location
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user.id


@patch("app.oauth")
def test_auth_google_username_collision_increments(mock_oauth, client, app):
    """auth/google picks unique username when base is taken."""
    from app.models import User, db

    with app.app_context():
        User.query.filter_by(email="other@example.com").delete()
        db.session.add(
            User(
                email="other@example.com",
                username="newuser",
                first_name="O",
                last_name="U",
            )
        )
        db.session.commit()
    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {
        "userinfo": {
            "email": "newuser@other.com",
            "given_name": "New",
            "family_name": "User",
        }
    }
    mock_oauth.google = mock_google
    response = client.get("/auth/google")
    assert response.status_code == 302
    with app.app_context():
        u = User.query.filter_by(email="newuser@other.com").first()
        assert u is not None
        assert u.username == "newuser1"


@patch("app.oauth")
def test_auth_google_new_user_gets_experiment_group(mock_oauth, client, app):
    """New users get assigned to control or experimental group."""
    from app.models import User

    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {
        "userinfo": {
            "email": "expuser@example.com",
            "given_name": "Exp",
            "family_name": "User",
        }
    }
    mock_oauth.google = mock_google

    response = client.get("/auth/google")
    assert response.status_code == 302

    with app.app_context():
        u = User.query.filter_by(email="expuser@example.com").first()
        assert u is not None
        assert u.experiment_group in ["control", "experimental"]


@patch("app.oauth")
def test_experiment_group_saved_in_session(mock_oauth, client):
    """Experiment group is stored in session after login."""
    mock_google = MagicMock()
    mock_google.authorize_access_token.return_value = {
        "userinfo": {
            "email": "sessionuser@example.com",
            "given_name": "Sess",
            "family_name": "User",
        }
    }
    mock_oauth.google = mock_google

    client.get("/auth/google")

    with client.session_transaction() as sess:
        assert sess.get("experiment_group") in ["control", "experimental"]
