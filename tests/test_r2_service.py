"""Tests for the R2 cloud storage service module."""

from unittest.mock import MagicMock, patch

from app.services import r2 as r2_service


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
