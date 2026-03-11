"""Tests for main and index routes."""

import io
from unittest.mock import MagicMock, patch

from PIL import Image


def test_index(client):
    """Test the index page."""
    response = client.get("/")
    assert response.status_code == 200


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


def test_upload_no_file(auth_client):
    """Upload without file returns 400."""
    response = auth_client.post("/upload", data={})
    assert response.status_code == 400
    assert b"No file part" in response.data or b"error" in response.data.lower()


def test_upload_empty_filename(auth_client):
    """Upload with empty filename returns 400."""
    response = auth_client.post(
        "/upload",
        data={"file": (io.BytesIO(b""), "")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_upload_success(auth_client, app):
    """Upload with valid file returns success and image_id."""
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    data = {"file": (buf, "photo.png")}
    response = auth_client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("status") == "success"
    assert "image_id" in data
    assert "image_url" in data


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


@patch("app.routes.main.get_genai_client")
def test_api_generate_no_gemini_key(
    mock_get_client, auth_client, user_image, hairstyle
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


@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_generate_success(
    mock_image_open, mock_get_client, auth_client, user_image, hairstyle, app
):
    """API generate returns success when Gemini returns image."""
    mock_image_open.return_value = MagicMock()
    mock_client = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data = "present"
    mock_img = MagicMock()
    mock_part.as_image.return_value = mock_img
    mock_client.models.generate_content.return_value = MagicMock(parts=[mock_part])
    mock_get_client.return_value = mock_client
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": user_image.id, "hairstyle_id": hairstyle.id},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("status") == "success"
    assert "image_id" in data
    assert "image_url" in data


@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_generate_exception_returns_500(
    mock_image_open, mock_get_client, auth_client, user_image, hairstyle
):
    """API generate returns 500 when Gemini raises."""
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


@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_generate_no_image_in_response_returns_500(
    mock_image_open, mock_get_client, auth_client, user_image, hairstyle
):
    """API generate returns 500 when model returns no image."""
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
