"""Tests for main and index routes."""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.models import UserImage, db


def test_index(client):
    """Test the index page."""
    response = client.get("/")
    assert response.status_code == 200
    assert b'href="/terms"' in response.data


def test_terms_page_public(client):
    """Terms page is public and renders required disclaimer content."""
    response = client.get("/terms")
    assert response.status_code == 200
    assert b"Terms &amp; Educational Disclaimer" in response.data
    assert b"Educational Prototype Disclaimer" in response.data
    assert b"No Liability" in response.data
    assert b"Service Interruptions" in response.data


def test_dashboard_redirect_unauthenticated(client):
    """Test that unauthorized users are redirected from the dashboard."""
    response = client.get("/dashboard")
    assert response.status_code == 302


def test_stylists_redirect_unauthenticated(client):
    """Stylists redirects to login when not authenticated."""
    response = client.get("/stylists")
    assert response.status_code == 302
    assert "/" in response.location or "login" in response.location


def test_style_studio_redirect_unauthenticated(client):
    """Style studio redirects when not logged in."""
    response = client.get("/style-studio")
    assert response.status_code == 302


def test_style_studio_authenticated(auth_client, hairstyle):
    """Style studio renders with hairstyles when logged in."""
    response = auth_client.get("/style-studio")
    assert response.status_code == 200
    assert b"Test Cut" in response.data or b"style" in response.data.lower()


def test_stylists_authenticated(auth_client, stylist):
    """Stylists page renders with stylists when logged in."""
    response = auth_client.get("/stylists")
    assert response.status_code == 200
    assert b"Jane Stylist" in response.data or b"stylist" in response.data.lower()


def test_stylists_search(auth_client, stylist):
    """Stylists search filters by query."""
    response = auth_client.get("/stylists?q=Jane")
    assert response.status_code == 200


def test_dashboard_admin(admin_client):
    """Dashboard loads for admin user."""
    response = admin_client.get("/dashboard")
    assert response.status_code == 200


def test_dashboard_non_admin_forbidden(auth_client):
    """Dashboard returns 403 for non-admin."""
    response = auth_client.get("/dashboard")
    assert response.status_code == 403


def test_result_redirect_unauthenticated(client):
    """Result page redirects when not logged in."""
    response = client.get("/result")
    assert response.status_code == 302


def test_result_no_image_id(auth_client):
    """Result with no image_id shows page or redirects (no generations)."""
    response = auth_client.get("/result")
    # 200 if template handles None, or 404/302 depending on implementation
    assert response.status_code in (200, 302, 404)


def test_result_with_invalid_image_id(auth_client):
    """Result with non-existent image_id returns 404."""
    response = auth_client.get("/result/99999")
    assert response.status_code == 404


def test_gallery_redirect_unauthenticated(client):
    """Gallery redirects when not logged in."""
    response = client.get("/gallery")
    assert response.status_code == 302


def test_gallery_authenticated(auth_client):
    """Gallery renders when logged in."""
    response = auth_client.get("/gallery")
    assert response.status_code == 200


def test_api_generate_redirect_unauthenticated(client):
    """API generate requires login."""
    response = client.post(
        "/api/generate",
        json={"user_image_id": 1, "hairstyle_id": 1},
        content_type="application/json",
    )
    assert response.status_code == 302


def test_api_generate_missing_params(auth_client):
    """API generate returns 400 when image or hairstyle missing."""
    response = auth_client.post(
        "/api/generate",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_api_generate_invalid_selection(auth_client):
    """API generate returns 400 for invalid image/hairstyle id."""
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": 99999, "hairstyle_id": 99999},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_generate_wrong_user_403(auth_client, hairstyle, app):
    """API generate returns 403 when image belongs to another user."""
    from app.models import User, UserImage, db

    with app.app_context():
        other = User(
            email="other@example.com",
            username="otheruser",
            first_name="O",
            last_name="U",
        )
        db.session.add(other)
        db.session.commit()
        oi = UserImage(user_id=other.id, image_url="uploads/other.jpg")
        db.session.add(oi)
        db.session.commit()
        oi_id = oi.id
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": oi_id, "hairstyle_id": hairstyle.id},
        content_type="application/json",
    )
    assert response.status_code == 403


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
def test_api_generate_no_gemini_key(
    mock_get_client, mock_download, auth_client, user_image, hairstyle
):
    """API generate returns 500 when Gemini API key is missing."""
    mock_get_client.return_value = None
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": user_image.id, "hairstyle_id": hairstyle.id},
        content_type="application/json",
    )
    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_generate_exception_returns_500(
    mock_image_open, mock_get_client, mock_download, auth_client, user_image, hairstyle
):
    """API generate returns 500 when Gemini raises."""
    mock_download.return_value = b"fake-bytes"
    mock_image_open.return_value = MagicMock()
    mock_get_client.return_value = MagicMock()
    mock_get_client.return_value.models.generate_content.side_effect = Exception(
        "API error"
    )
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": user_image.id, "hairstyle_id": hairstyle.id},
        content_type="application/json",
    )
    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_generate_no_image_in_response_returns_500(
    mock_image_open, mock_get_client, mock_download, auth_client, user_image, hairstyle
):
    """API generate returns 500 when model returns no image."""
    mock_download.return_value = b"fake-bytes"
    mock_image_open.return_value = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parts=[])
    mock_get_client.return_value = mock_client
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": user_image.id, "hairstyle_id": hairstyle.id},
        content_type="application/json",
    )
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# R2 presign / confirm endpoint tests
# ---------------------------------------------------------------------------


def _r2_auth_client(app):
    """Create an authenticated test client using the app."""
    from app.models import User, db

    client = app.test_client()
    with app.app_context():
        u = User(
            email="r2user@example.com",
            username="r2user",
            first_name="R2",
            last_name="User",
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    return client, uid


@patch("app.services.r2.get_presigned_put_url")
@patch("app.services.r2.make_upload_key")
def test_presign_returns_put_url(mock_key, mock_presign, app):
    """POST /api/upload/presign returns put_url and upload_key."""
    mock_key.return_value = "uploads/abc_photo.jpg"
    mock_presign.return_value = "https://r2.example.com/put"
    ac, _ = _r2_auth_client(app)

    response = ac.post(
        "/api/upload/presign",
        json={"filename": "photo.jpg", "content_type": "image/jpeg"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["put_url"] == "https://r2.example.com/put"
    assert data["upload_key"] == "uploads/abc_photo.jpg"


def test_presign_rejects_bad_content_type(app):
    """POST /api/upload/presign rejects unsupported content types."""
    ac, _ = _r2_auth_client(app)
    response = ac.post(
        "/api/upload/presign",
        json={"filename": "file.txt", "content_type": "text/plain"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert b"Unsupported" in response.data


def test_presign_requires_auth(app):
    """POST /api/upload/presign redirects when not authenticated."""
    client = app.test_client()
    response = client.post(
        "/api/upload/presign",
        json={"filename": "photo.jpg"},
        content_type="application/json",
    )
    assert response.status_code == 302


@patch("app.services.r2.get_display_url")
def test_confirm_creates_user_image(mock_display, app):
    """POST /api/upload/confirm creates a UserImage and returns display URL."""
    mock_display.return_value = "https://r2.example.com/get/uploads/abc.jpg"
    ac, uid = _r2_auth_client(app)

    response = ac.post(
        "/api/upload/confirm",
        json={"upload_key": "uploads/abc_photo.jpg"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["image_url"] == "https://r2.example.com/get/uploads/abc.jpg"
    assert "image_id" in data

    with app.app_context():
        ui = db.session.get(UserImage, data["image_id"])
        assert ui is not None
        assert ui.image_url == "uploads/abc_photo.jpg"
        assert ui.user_id == uid


def test_confirm_rejects_invalid_key(app):
    """POST /api/upload/confirm rejects keys without uploads/ prefix."""
    ac, _ = _r2_auth_client(app)
    response = ac.post(
        "/api/upload/confirm",
        json={"upload_key": "malicious/path"},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_confirm_rejects_missing_key(app):
    """POST /api/upload/confirm rejects missing upload_key."""
    ac, _ = _r2_auth_client(app)
    response = ac.post(
        "/api/upload/confirm",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# R2-enabled generate tests
# ---------------------------------------------------------------------------


@patch("app.services.r2.get_display_url")
@patch("app.services.r2.upload_bytes")
@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
def test_api_generate_success(
    mock_get_client, mock_download, mock_upload, mock_display, app
):
    """Generate reads from R2, uploads result, returns presigned URL."""
    from app.models import Hairstyle, User, UserImage, db

    ac = app.test_client()
    with app.app_context():
        u = User(
            email="gen@example.com",
            username="genuser",
            first_name="Gen",
            last_name="User",
        )
        db.session.add(u)
        db.session.commit()
        h = Hairstyle(
            name="R2 Cut",
            description="A test style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(user_id=u.id, image_url="uploads/selfie.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        uid, ui_id, h_id = u.id, ui.id, h.id

    with ac.session_transaction() as sess:
        sess["user_id"] = uid

    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mock_download.return_value = buf.getvalue()

    mock_part = MagicMock()
    mock_part.inline_data = MagicMock(data=buf.getvalue(), mime_type="image/png")
    mock_part.as_image.return_value = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parts=[mock_part])
    mock_get_client.return_value = mock_client

    mock_display.return_value = "https://r2.example.com/get/result.webp"

    response = ac.post(
        "/api/generate",
        json={"user_image_id": ui_id, "hairstyle_id": h_id},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["image_url"] == "https://r2.example.com/get/result.webp"

    mock_download.assert_called_once_with("uploads/selfie.jpg")
    mock_upload.assert_called_once()

    uploaded_key = mock_upload.call_args[0][0]
    uploaded_mime = mock_upload.call_args[0][2]
    assert uploaded_key.endswith(".webp")
    assert uploaded_mime == "image/webp"


# ---------------------------------------------------------------------------
# R2-enabled result / gallery display URL tests
# ---------------------------------------------------------------------------


@patch("app.services.r2.get_display_url")
def test_result_uses_r2_display_url(mock_display, app):
    """Result page passes presigned URL to template."""
    from app.models import GeneratedImage, Hairstyle, User, UserImage, db

    ac = app.test_client()
    with app.app_context():
        u = User(
            email="res@example.com",
            username="resuser",
            first_name="R",
            last_name="U",
        )
        db.session.add(u)
        db.session.commit()
        h = Hairstyle(
            name="Res Cut",
            description="A style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(user_id=u.id, image_url="uploads/photo.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        gi = GeneratedImage(
            user_id=u.id,
            user_image_id=ui.id,
            hairstyle_id=h.id,
            image_url="uploads/gen_result.webp",
        )
        db.session.add(gi)
        db.session.commit()
        uid, gi_id = u.id, gi.id

    with ac.session_transaction() as sess:
        sess["user_id"] = uid

    mock_display.return_value = "https://r2.example.com/display/gen_result.webp"

    response = ac.get(f"/result/{gi_id}")
    assert response.status_code == 200
    assert b"https://r2.example.com/display/gen_result.webp" in response.data


@patch("app.services.r2.get_display_url")
def test_gallery_uses_r2_display_urls(mock_display, app):
    """Gallery passes presigned URLs for all images."""
    from app.models import GeneratedImage, Hairstyle, User, UserImage, db

    ac = app.test_client()
    with app.app_context():
        u = User(
            email="gal@example.com",
            username="galuser",
            first_name="G",
            last_name="U",
        )
        db.session.add(u)
        db.session.commit()
        h = Hairstyle(
            name="Gal Cut",
            description="A style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(user_id=u.id, image_url="uploads/photo.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        gi = GeneratedImage(
            user_id=u.id,
            user_image_id=ui.id,
            hairstyle_id=h.id,
            image_url="uploads/gen_gal.webp",
        )
        db.session.add(gi)
        db.session.commit()
        uid = u.id

    with ac.session_transaction() as sess:
        sess["user_id"] = uid

    mock_display.return_value = "https://r2.example.com/display/gen_gal.webp"

    response = ac.get("/gallery")
    assert response.status_code == 200
    assert b"https://r2.example.com/display/gen_gal.webp" in response.data


# ---------------------------------------------------------------------------
# POST /api/rate
# ---------------------------------------------------------------------------


def test_api_rate_redirect_unauthenticated(client):
    """Unauthenticated users cannot rate (returns 401)."""
    response = client.post(
        "/api/rate",
        json={"generated_image_id": 1, "rating": 3},
        content_type="application/json",
    )
    assert response.status_code == 401


def test_api_rate_stores_rating(auth_client, generated_image, app):
    """Valid 1–5 rating is stored for the user's generated image."""
    response = auth_client.post(
        "/api/rate",
        json={"generated_image_id": generated_image.id, "rating": 5},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "success", "rating": 5}

    from app.models import Rating

    with app.app_context():
        row = Rating.query.filter_by(generated_image_id=generated_image.id).one()
        assert row.rating == 5
        assert row.user_id == generated_image.user_id


@pytest.mark.parametrize("bad_rating", [0, 6, -1])
def test_api_rate_rejects_out_of_range(auth_client, generated_image, bad_rating):
    """Ratings outside 1–5 return 400."""
    response = auth_client.post(
        "/api/rate",
        json={"generated_image_id": generated_image.id, "rating": bad_rating},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_rate_other_users_image_403(auth_client, generated_image, app, hairstyle):
    """Rating another user's generated image returns 403."""
    from app.models import User, UserImage, db

    with app.app_context():
        other = User(
            email="rateother@example.com",
            username="rateother",
            first_name="O",
            last_name="T",
        )
        db.session.add(other)
        db.session.commit()
        oi = UserImage(user_id=other.id, image_url="uploads/other_rate.jpg")
        db.session.add(oi)
        db.session.commit()
        from app.models import GeneratedImage

        theirs = GeneratedImage(
            user_id=other.id,
            user_image_id=oi.id,
            hairstyle_id=hairstyle.id,
            image_url="uploads/theirs.webp",
        )
        db.session.add(theirs)
        db.session.commit()
        their_id = theirs.id

    response = auth_client.post(
        "/api/rate",
        json={"generated_image_id": their_id, "rating": 4},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_api_rate_updates_existing(auth_client, generated_image, app):
    """Re-rating the same image updates the row instead of creating a duplicate."""
    from app.models import Rating

    auth_client.post(
        "/api/rate",
        json={"generated_image_id": generated_image.id, "rating": 2},
        content_type="application/json",
    )
    auth_client.post(
        "/api/rate",
        json={"generated_image_id": generated_image.id, "rating": 5},
        content_type="application/json",
    )

    with app.app_context():
        assert (
            Rating.query.filter_by(generated_image_id=generated_image.id).count() == 1
        )
        assert (
            Rating.query.filter_by(generated_image_id=generated_image.id).one().rating
            == 5
        )
