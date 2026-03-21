"""Tests for the R2 cloud storage service module."""

from unittest.mock import MagicMock, patch

from app.services import r2 as r2_service


def test_make_upload_key_format(app):
    """Upload key has uploads/ prefix and sanitized filename."""
    with app.app_context():
        key = r2_service.make_upload_key("my photo.png")
        assert key.startswith("uploads/")
        assert "my_photo.png" in key


def test_make_upload_key_default_when_empty(app):
    """Upload key falls back to 'photo' when filename is empty."""
    with app.app_context():
        key = r2_service.make_upload_key("")
        assert key.startswith("uploads/")
        assert "photo" in key


def test_make_generated_key_format(app):
    """Generated key has uploads/gen_ prefix and .webp extension."""
    with app.app_context():
        key = r2_service.make_generated_key()
        assert key.startswith("uploads/gen_")
        assert key.endswith(".webp")


def test_make_upload_key_unique(app):
    """Two calls produce different keys."""
    with app.app_context():
        k1 = r2_service.make_upload_key("photo.jpg")
        k2 = r2_service.make_upload_key("photo.jpg")
        assert k1 != k2


@patch("app.services.r2._get_s3_client")
def test_get_presigned_put_url(mock_client_fn, app):
    """get_presigned_put_url calls generate_presigned_url with put_object."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://r2.example.com/put"
    mock_client_fn.return_value = mock_client

    with app.app_context():
        url = r2_service.get_presigned_put_url("uploads/test.jpg", "image/jpeg")

    assert url == "https://r2.example.com/put"
    mock_client.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "uploads/test.jpg",
            "ContentType": "image/jpeg",
        },
        ExpiresIn=3600,
    )


@patch("app.services.r2._get_s3_client")
def test_get_presigned_get_url(mock_client_fn, app):
    """get_presigned_get_url calls generate_presigned_url with get_object."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://r2.example.com/get"
    mock_client_fn.return_value = mock_client

    with app.app_context():
        url = r2_service.get_presigned_get_url("uploads/test.jpg")

    assert url == "https://r2.example.com/get"
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "uploads/test.jpg",
        },
        ExpiresIn=3600,
    )


@patch("app.services.r2._get_s3_client")
def test_upload_bytes(mock_client_fn, app):
    """upload_bytes calls put_object with correct params."""
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client

    with app.app_context():
        r2_service.upload_bytes("uploads/gen_abc.webp", b"fake-image", "image/webp")

    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="uploads/gen_abc.webp",
        Body=b"fake-image",
        ContentType="image/webp",
    )


@patch("app.services.r2._get_s3_client")
def test_download_bytes(mock_client_fn, app):
    """download_bytes returns object body bytes."""
    mock_body = MagicMock()
    mock_body.read.return_value = b"image-data"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_body}
    mock_client_fn.return_value = mock_client

    with app.app_context():
        data = r2_service.download_bytes("uploads/test.jpg")

    assert data == b"image-data"
    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="uploads/test.jpg",
    )


@patch("app.services.r2._get_s3_client")
def test_get_display_url(mock_client_fn, app):
    """get_display_url returns a presigned GET URL."""
    mock_client = MagicMock()
    mock_client.generate_presigned_url.return_value = "https://r2.example.com/display"
    mock_client_fn.return_value = mock_client

    with app.app_context():
        url = r2_service.get_display_url("uploads/test.jpg")

    assert url == "https://r2.example.com/display"


def test_get_display_url_none_for_falsy(app):
    """get_display_url returns None for empty/None image_url."""
    with app.app_context():
        assert r2_service.get_display_url(None) is None
        assert r2_service.get_display_url("") is None
