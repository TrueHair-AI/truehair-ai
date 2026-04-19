"""Tests for main and index routes."""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.models import (
    Consent,
    ExperimentSession,
    UserImage,
    db,
)


def _consent_and_login(app, client, experiment_group="control"):
    """Helper: create a Consent + ExperimentSession and attach the session_id to client."""
    sid = str(uuid.uuid4())
    with app.app_context():
        db.session.add(
            Consent(session_id=sid, full_name="", experiment_group=experiment_group)
        )
        db.session.add(
            ExperimentSession(
                session_id=sid,
                experiment_group=experiment_group,
                started_at=datetime.now(timezone.utc),
                last_ping_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()
    with client.session_transaction() as sess:
        sess["session_id"] = sid
    return sid


# ---------------------------------------------------------------------------
# Index / consent gating
# ---------------------------------------------------------------------------


def test_index_redirects_to_consent_for_unconsented(client):
    """/ redirects to /consent when no session cookie is set."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/consent" in response.location


def test_index_redirects_to_style_studio_when_consented(auth_client):
    """/ redirects to /style-studio when the session has consented."""
    response = auth_client.get("/")
    assert response.status_code == 302
    assert "style-studio" in response.location


def test_consent_page_renders(client):
    """GET /consent renders the consent page."""
    response = client.get("/consent")
    assert response.status_code == 200
    assert b"I Agree" in response.data


def test_submit_consent_creates_records_and_redirects(app, client):
    """POST /consent creates a Consent + ExperimentSession row and sets the session cookie."""
    response = client.post("/consent")
    assert response.status_code == 302
    assert "style-studio" in response.location

    with client.session_transaction() as sess:
        sid = sess.get("session_id")
    assert sid is not None

    with app.app_context():
        assert Consent.query.filter_by(session_id=sid).first() is not None
        assert ExperimentSession.query.filter_by(session_id=sid).first() is not None


def test_submit_consent_is_idempotent(app, auth_client):
    """POST /consent twice doesn't create a second Consent row."""
    with auth_client.session_transaction() as sess:
        sid = sess["session_id"]
    auth_client.post("/consent")
    with app.app_context():
        assert Consent.query.filter_by(session_id=sid).count() == 1


def test_terms_page_public(client):
    """Terms page is public and renders required disclaimer content."""
    response = client.get("/terms")
    assert response.status_code == 200
    assert b"Terms &amp; Educational Disclaimer" in response.data
    assert b"Educational Prototype Disclaimer" in response.data
    assert b"No Liability" in response.data
    assert b"Service Interruptions" in response.data


# ---------------------------------------------------------------------------
# Consent-gated routes redirect to /consent when unconsented
# ---------------------------------------------------------------------------


def test_stylists_redirect_unconsented(client):
    response = client.get("/stylists")
    assert response.status_code == 302
    assert "/consent" in response.location


def test_style_studio_redirect_unconsented(client):
    response = client.get("/style-studio")
    assert response.status_code == 302
    assert "/consent" in response.location


def test_style_studio_consented(auth_client, hairstyle):
    response = auth_client.get("/style-studio")
    assert response.status_code == 200
    assert b"Test Cut" in response.data or b"style" in response.data.lower()


def test_stylists_consented(auth_client, stylist):
    response = auth_client.get("/stylists")
    assert response.status_code == 200
    assert b"Jane Stylist" in response.data or b"stylist" in response.data.lower()


def test_stylists_search(auth_client, stylist):
    response = auth_client.get("/stylists?q=Jane")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dashboard + export (ungated pending issue #16).
# ---------------------------------------------------------------------------


def test_dashboard_renders(client):
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_admin_export_json(app, client):
    _consent_and_login(app, client)
    response = client.get("/api/admin/export?format=json")
    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 1

    row = data[0]
    assert "participant_id" in row
    assert "experiment_group" in row
    assert "num_visualizations" in row
    assert "avg_rating" in row
    assert "num_ratings" in row
    assert "session_duration_seconds" in row
    assert "styles_selected" in row
    assert "consented_at" in row

    # Ensure no PII is exposed
    assert "email" not in row
    assert "username" not in row
    assert "first_name" not in row
    assert "last_name" not in row


def test_admin_export_csv(app, client):
    _consent_and_login(app, client)
    response = client.get("/api/admin/export")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]

    csv_data = response.data.decode("utf-8")
    assert "participant_id" in csv_data
    assert "experiment_group" in csv_data


def test_admin_export_iterates_experiment_sessions(app, client):
    """Export emits one row per ExperimentSession row."""
    _consent_and_login(app, client, experiment_group="control")
    _consent_and_login(app, client, experiment_group="experimental")
    response = client.get("/api/admin/export?format=json")
    data = response.get_json()
    assert len(data) == 2


def test_admin_export_invalid_format(client):
    response = client.get("/api/admin/export?format=xml")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Result + gallery
# ---------------------------------------------------------------------------


def test_result_redirect_unconsented(client):
    response = client.get("/result")
    assert response.status_code == 302


def test_result_no_image_id(auth_client):
    response = auth_client.get("/result")
    assert response.status_code in (200, 302, 404)


def test_result_with_invalid_image_id(auth_client):
    response = auth_client.get("/result/99999")
    assert response.status_code == 404


def test_gallery_redirect_unconsented(client):
    response = client.get("/gallery")
    assert response.status_code == 302


def test_gallery_consented(auth_client):
    response = auth_client.get("/gallery")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------


def test_api_generate_redirect_unconsented(client):
    response = client.post(
        "/api/generate",
        json={"user_image_id": 1, "hairstyle_id": 1},
        content_type="application/json",
    )
    assert response.status_code == 302


def test_api_generate_missing_params(auth_client):
    response = auth_client.post(
        "/api/generate",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_api_generate_invalid_selection(auth_client):
    response = auth_client.post(
        "/api/generate",
        json={"user_image_id": 99999, "hairstyle_id": 99999},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_generate_wrong_session_403(app, auth_client, hairstyle):
    """Generate returns 403 when the user_image belongs to another session."""
    other_sid = str(uuid.uuid4())
    with app.app_context():
        oi = UserImage(session_id=other_sid, image_url="uploads/other.jpg")
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
# R2 presign / confirm
# ---------------------------------------------------------------------------


@patch("app.services.r2.get_presigned_put_url")
@patch("app.services.r2.make_upload_key")
def test_presign_returns_put_url(mock_key, mock_presign, auth_client):
    mock_key.return_value = "uploads/abc_photo.jpg"
    mock_presign.return_value = "https://r2.example.com/put"
    response = auth_client.post(
        "/api/upload/presign",
        json={"filename": "photo.jpg", "content_type": "image/jpeg"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["put_url"] == "https://r2.example.com/put"
    assert data["upload_key"] == "uploads/abc_photo.jpg"


def test_presign_rejects_bad_content_type(auth_client):
    response = auth_client.post(
        "/api/upload/presign",
        json={"filename": "file.txt", "content_type": "text/plain"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert b"Unsupported" in response.data


def test_presign_redirects_unconsented(client):
    response = client.post(
        "/api/upload/presign",
        json={"filename": "photo.jpg"},
        content_type="application/json",
    )
    assert response.status_code == 302


@patch("app.services.r2.get_display_url")
def test_confirm_creates_user_image(mock_display, app, auth_client):
    mock_display.return_value = "https://r2.example.com/get/uploads/abc.jpg"
    with auth_client.session_transaction() as sess:
        sid = sess["session_id"]
    response = auth_client.post(
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
        assert ui.session_id == sid


def test_confirm_rejects_invalid_key(auth_client):
    response = auth_client.post(
        "/api/upload/confirm",
        json={"upload_key": "malicious/path"},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_confirm_rejects_missing_key(auth_client):
    response = auth_client.post(
        "/api/upload/confirm",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Generate + R2 success path
# ---------------------------------------------------------------------------


@patch("app.services.r2.get_display_url")
@patch("app.services.r2.upload_bytes")
@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
def test_api_generate_success(
    mock_get_client, mock_download, mock_upload, mock_display, app, client
):
    from app.models import Hairstyle

    sid = _consent_and_login(app, client)
    with app.app_context():
        h = Hairstyle(
            name="R2 Cut",
            description="A test style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(session_id=sid, image_url="uploads/selfie.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        ui_id, h_id = ui.id, h.id

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

    response = client.post(
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
# Result / gallery display URL tests
# ---------------------------------------------------------------------------


@patch("app.services.r2.get_display_url")
def test_result_uses_r2_display_url(mock_display, app, client):
    from app.models import GeneratedImage, Hairstyle

    sid = _consent_and_login(app, client)
    with app.app_context():
        h = Hairstyle(
            name="Res Cut",
            description="A style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(session_id=sid, image_url="uploads/photo.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        gi = GeneratedImage(
            session_id=sid,
            user_image_id=ui.id,
            hairstyle_id=h.id,
            image_url="uploads/gen_result.webp",
        )
        db.session.add(gi)
        db.session.commit()
        gi_id = gi.id

    mock_display.return_value = "https://r2.example.com/display/gen_result.webp"

    response = client.get(f"/result/{gi_id}")
    assert response.status_code == 200
    assert b"https://r2.example.com/display/gen_result.webp" in response.data


@patch("app.services.r2.get_display_url")
def test_gallery_uses_r2_display_urls(mock_display, app, client):
    from app.models import GeneratedImage, Hairstyle

    sid = _consent_and_login(app, client)
    with app.app_context():
        h = Hairstyle(
            name="Gal Cut",
            description="A style",
            category="MODERN",
            image_url="test.png",
        )
        ui = UserImage(session_id=sid, image_url="uploads/photo.jpg")
        db.session.add_all([h, ui])
        db.session.commit()
        gi = GeneratedImage(
            session_id=sid,
            user_image_id=ui.id,
            hairstyle_id=h.id,
            image_url="uploads/gen_gal.webp",
        )
        db.session.add(gi)
        db.session.commit()

    mock_display.return_value = "https://r2.example.com/display/gen_gal.webp"

    response = client.get("/gallery")
    assert response.status_code == 200
    assert b"https://r2.example.com/display/gen_gal.webp" in response.data


# ---------------------------------------------------------------------------
# POST /api/rate
# ---------------------------------------------------------------------------


def test_api_rate_unauthenticated_returns_401(client):
    """Unauthenticated users cannot rate (returns 401)."""
    response = client.post(
        "/api/rate",
        json={"generated_image_id": 1, "rating": 3},
        content_type="application/json",
    )
    assert response.status_code == 401


def test_api_rate_stores_rating(auth_client, generated_image, app):
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
        assert row.session_id == generated_image.session_id


@pytest.mark.parametrize("bad_rating", [0, 6, -1])
def test_api_rate_rejects_out_of_range(auth_client, generated_image, bad_rating):
    response = auth_client.post(
        "/api/rate",
        json={"generated_image_id": generated_image.id, "rating": bad_rating},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_rate_other_session_image_403(app, auth_client, hairstyle):
    """Rating an image owned by a different session returns 403."""
    from app.models import GeneratedImage

    other_sid = str(uuid.uuid4())
    with app.app_context():
        oi = UserImage(session_id=other_sid, image_url="uploads/other_rate.jpg")
        db.session.add(oi)
        db.session.commit()
        theirs = GeneratedImage(
            session_id=other_sid,
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


# ---------------------------------------------------------------------------
# Session start / ping / end
# ---------------------------------------------------------------------------


def test_api_session_start_unconsented(client):
    response = client.post("/api/session/start")
    assert response.status_code == 302


def test_api_session_start_creates_session(auth_client, app):
    response = auth_client.post("/api/session/start")
    assert response.status_code == 200
    data = response.get_json()
    assert "session_id" in data

    with app.app_context():
        session_record = db.session.get(ExperimentSession, data["session_id"])
        assert session_record is not None
        assert session_record.ended_at is None


def test_api_session_start_returns_existing(auth_client, app):
    response1 = auth_client.post("/api/session/start")
    data1 = response1.get_json()

    response2 = auth_client.post("/api/session/start")
    data2 = response2.get_json()

    assert data1["session_id"] == data2["session_id"]


def test_api_session_ping_updates_last_ping(auth_client, app):
    start_response = auth_client.post("/api/session/start")
    session_pk = start_response.get_json()["session_id"]

    with app.app_context():
        session_record = db.session.get(ExperimentSession, session_pk)
        original_ping = session_record.last_ping_at

    import time

    time.sleep(0.1)

    ping_response = auth_client.post(
        "/api/session/ping",
        json={"session_id": session_pk},
        content_type="application/json",
    )
    assert ping_response.status_code == 200

    with app.app_context():
        session_record = db.session.get(ExperimentSession, session_pk)
        assert session_record.last_ping_at > original_ping


def test_api_session_end_computes_duration(auth_client, app):
    start_response = auth_client.post("/api/session/start")
    session_pk = start_response.get_json()["session_id"]

    end_response = auth_client.post(
        "/api/session/end",
        json={"session_id": session_pk},
        content_type="application/json",
    )
    assert end_response.status_code == 200

    with app.app_context():
        session_record = db.session.get(ExperimentSession, session_pk)
        assert session_record.ended_at is not None
        assert session_record.duration_seconds is not None


# ---------------------------------------------------------------------------
# POST /api/recommend
# ---------------------------------------------------------------------------


def test_api_recommend_redirect_unconsented(client):
    response = client.post(
        "/api/recommend",
        json={"user_image_id": 1},
        content_type="application/json",
    )
    assert response.status_code == 302


def test_api_recommend_control_group_forbidden(auth_client):
    """Control-group sessions get 403 on /api/recommend."""
    response = auth_client.post(
        "/api/recommend",
        json={"user_image_id": 1},
        content_type="application/json",
    )
    assert response.status_code == 403


def test_api_recommend_missing_user_image(experimental_client):
    client, _sid = experimental_client
    response = client.post(
        "/api/recommend",
        json={},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_recommend_wrong_session_403(app, experimental_client):
    client, _sid = experimental_client
    other_sid = str(uuid.uuid4())
    with app.app_context():
        oi = UserImage(session_id=other_sid, image_url="uploads/other_rec.jpg")
        db.session.add(oi)
        db.session.commit()
        oi_id = oi.id

    response = client.post(
        "/api/recommend",
        json={"user_image_id": oi_id},
        content_type="application/json",
    )
    assert response.status_code == 403


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
def test_api_recommend_no_gemini_key(
    mock_get_client, mock_download, app, experimental_client
):
    client, sid = experimental_client
    with app.app_context():
        ui = UserImage(session_id=sid, image_url="uploads/rec_photo.jpg")
        db.session.add(ui)
        db.session.commit()
        ui_id = ui.id

    mock_get_client.return_value = None
    response = client.post(
        "/api/recommend",
        json={"user_image_id": ui_id},
        content_type="application/json",
    )
    assert response.status_code == 500


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_recommend_exception_returns_500(
    mock_image_open, mock_get_client, mock_download, app, experimental_client
):
    client, sid = experimental_client
    with app.app_context():
        ui = UserImage(session_id=sid, image_url="uploads/rec_photo.jpg")
        db.session.add(ui)
        db.session.commit()
        ui_id = ui.id

    mock_download.return_value = b"fake-bytes"
    mock_image_open.return_value = MagicMock()
    mock_get_client.return_value = MagicMock()
    mock_get_client.return_value.models.generate_content.side_effect = Exception(
        "API error"
    )
    response = client.post(
        "/api/recommend",
        json={"user_image_id": ui_id},
        content_type="application/json",
    )
    assert response.status_code == 500


@patch("app.services.r2.download_bytes")
@patch("app.routes.main.get_genai_client")
@patch("app.routes.main.Image.open")
def test_api_recommend_success(
    mock_image_open, mock_get_client, mock_download, app, experimental_client, hairstyle
):
    import json

    client, sid = experimental_client
    with app.app_context():
        ui = UserImage(session_id=sid, image_url="uploads/rec_photo.jpg")
        db.session.add(ui)
        db.session.commit()
        ui_id = ui.id

    mock_download.return_value = b"fake-bytes"
    mock_image_open.return_value = MagicMock()
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {
            "recommendations": [
                {
                    "hairstyle_id": hairstyle.id,
                    "reasoning": "This is a great style for you.",
                }
            ]
        }
    )
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    response = client.post(
        "/api/recommend",
        json={"user_image_id": ui_id},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["hairstyle_id"] == hairstyle.id

    from app.models import Recommendation

    with app.app_context():
        rec = Recommendation.query.filter_by(user_image_id=ui_id).first()
        assert rec is not None
        assert rec.hairstyle_id == hairstyle.id
        assert rec.reasoning == "This is a great style for you."
