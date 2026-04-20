"""Tests for main and index routes."""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.routes.main import get_genai_client
from app.models import (
    Consent,
    ExperimentSession,
    GeneratedImage,
    db,
)


def make_test_image():
    from PIL import Image

    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _consent_and_login(app, client, experiment_group="control"):
    """Helper: create a Consent + ExperimentSession and attach the session_id to client."""
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
    with client.session_transaction() as sess:
        sess["session_id"] = sid
    return sid


def test_get_genai_client_uses_vertex_ai_config(app):
    """get_genai_client configures Vertex AI using the Flask app config."""
    with app.app_context():
        app.config["GOOGLE_CLOUD_PROJECT"] = "test-project"
        app.config["GOOGLE_CLOUD_LOCATION"] = "europe-west4"

        with patch("app.routes.main.genai.Client") as mock_client:
            client = get_genai_client()

            mock_client.assert_called_once_with(
                vertexai=True,
                project="test-project",
                location="europe-west4",
            )
            assert client is mock_client.return_value


def test_get_genai_client_returns_none_if_no_project(app):
    """get_genai_client returns None when the project is missing."""
    with app.app_context():
        app.config["GOOGLE_CLOUD_PROJECT"] = None

        client = get_genai_client()

    assert client is None


def test_get_genai_client_returns_none_on_client_init_error(app):
    """get_genai_client returns None when client initialization raises."""
    with app.app_context():
        app.config["GOOGLE_CLOUD_PROJECT"] = "test-project"
        app.config["GOOGLE_CLOUD_LOCATION"] = "us-central1"

        with patch("app.routes.main.genai.Client", side_effect=Exception("boom")):
            client = get_genai_client()

    assert client is None


# ---------------------------------------------------------------------------
# Index / consent gating
# ---------------------------------------------------------------------------


def test_index_renders_landing_for_unconsented(client):
    """/ renders landing page with a CTA to /consent when no session cookie is set."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"What this is" in response.data
    assert b'href="/consent"' in response.data


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
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302


def test_api_recommend_control_group_forbidden(auth_client):
    """Control-group sessions get 403 on /api/recommend."""
    response = auth_client.post(
        "/api/recommend",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403


def test_api_recommend_missing_photo(experimental_client):
    client, _sid = experimental_client
    response = client.post(
        "/api/recommend",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


@patch("app.routes.main.get_genai_client")
def test_api_recommend_no_gemini_key(mock_get_client, app, experimental_client):
    client, _sid = experimental_client

    mock_get_client.return_value = None
    response = client.post(
        "/api/recommend",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_recommend_exception_returns_500(mock_get_client, app, experimental_client):
    client, _sid = experimental_client

    mock_get_client.return_value = MagicMock()
    mock_get_client.return_value.models.generate_content.side_effect = Exception(
        "API error"
    )
    response = client.post(
        "/api/recommend",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_recommend_success(mock_get_client, app, experimental_client, hairstyle):
    import json

    client, sid = experimental_client

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
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["hairstyle_id"] == hairstyle.id

    from app.models import Recommendation

    with app.app_context():
        rec = Recommendation.query.filter_by(session_id=sid).first()
        assert rec is not None
        assert rec.hairstyle_id == hairstyle.id
        assert rec.reasoning == "This is a great style for you."


@patch("app.routes.main.get_genai_client")
def test_api_generate_success(mock_get_client, app, auth_client, hairstyle):
    from PIL import Image

    # Create fake image
    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    mock_part = MagicMock()
    mock_part.inline_data = MagicMock(data=buf.getvalue(), mime_type="image/png")

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parts=[mock_part])
    mock_get_client.return_value = mock_client

    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (buf, "test.png"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert len(response.data) > 0

    gen_id = response.headers.get("X-Generated-Image-Id")
    assert gen_id is not None
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, int(gen_id))
        assert gen_img is not None
        assert gen_img.hairstyle_id == hairstyle.id


# ---------------------------------------------------------------------------
# Upload validation (size / MIME / corruption) for /api/generate and /api/recommend
# ---------------------------------------------------------------------------


def test_api_generate_rejects_bad_mimetype(auth_client, hairstyle):
    """A file declared as application/pdf is rejected before decoding."""
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (io.BytesIO(b"%PDF-1.4 fake"), "test.pdf", "application/pdf"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Unsupported file type" in response.data


def test_api_generate_rejects_corrupted_bytes(auth_client, hairstyle):
    """A non-image byte stream declared as image/jpeg is rejected by PIL.verify()."""
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (io.BytesIO(b"not-an-image"), "test.jpg", "image/jpeg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Invalid or corrupted" in response.data


def test_api_generate_rejects_large_file(auth_client, hairstyle):
    """Flask's MAX_CONTENT_LENGTH (10MB) rejects oversize uploads with 413."""
    oversize = io.BytesIO(b"\x00" * (10 * 1024 * 1024 + 1024))
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (oversize, "big.jpg", "image/jpeg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 413


def test_api_recommend_rejects_bad_mimetype(experimental_client):
    client, _sid = experimental_client
    response = client.post(
        "/api/recommend",
        data={
            "photo": (io.BytesIO(b"%PDF-1.4 fake"), "test.pdf", "application/pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Unsupported file type" in response.data


def test_api_recommend_rejects_corrupted_bytes(experimental_client):
    client, _sid = experimental_client
    response = client.post(
        "/api/recommend",
        data={
            "photo": (io.BytesIO(b"not-an-image"), "test.jpg", "image/jpeg"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Invalid or corrupted" in response.data


# ---------------------------------------------------------------------------
# /api/rate cross-session isolation
# ---------------------------------------------------------------------------


def test_api_rate_other_session_image_403(app, auth_client, hairstyle):
    """Rating an image owned by a different session returns 403."""
    other_sid = str(uuid.uuid4())
    with app.app_context():
        theirs = GeneratedImage(
            session_id=other_sid,
            hairstyle_id=hairstyle.id,
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
