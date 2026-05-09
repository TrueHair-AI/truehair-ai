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
    Stylist,
    db,
)


def make_test_image():
    from PIL import Image

    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _make_participant_data(app, experiment_group="control"):
    """Create a Consent + ExperimentSession row pair (participant export data)."""
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
    """/ renders the consumer landing page with a CTA to /login when no session cookie is set."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"See yourself in any hairstyle, instantly." in response.data
    assert b'href="/login"' in response.data


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
    """Terms page is public and renders the consumer ToS sections."""
    response = client.get("/terms")
    assert response.status_code == 200
    body = response.data
    assert b"Terms of Service" in body
    assert b"Acceptance of these Terms" in body
    assert b"Acceptable use" in body
    # Acceptable Use must call out third-party photo consent — moved here from
    # the deleted IRB consent doc.
    assert b"Do not upload images of other people without their consent" in body
    assert b"Disclaimers and limitation of liability" in body
    assert b"Governing law" in body


def test_terms_page_drops_irb_framing(client):
    """Consumer ToS rewrite must not leak IRB / research-study / course-project framing."""
    response = client.get("/terms")
    assert response.status_code == 200
    text = response.data.lower()
    assert b"irb" not in text
    assert b"research study" not in text
    assert b"course project" not in text
    assert b"educational prototype" not in text


def test_login_page_renders_terms_modal(client):
    """/login renders the first-visit Terms modal markup; JS gates visibility on localStorage."""
    response = client.get("/login")
    assert response.status_code == 200
    body = response.data
    # Modal container, dialog role, and accept button are all present in the
    # initial markup so the JS can show/hide it without a re-render.
    assert b'id="termsModal"' in body
    assert b'role="dialog"' in body
    assert b'aria-modal="true"' in body
    assert b'id="termsAcceptBtn"' in body
    assert b"I agree, continue" in body
    # The localStorage key is versioned so we can re-prompt later if Terms change.
    assert b"terms_accepted_v1" in body
    # Google sign-in button has the id the gating JS toggles.
    assert b'id="googleLoginBtn"' in body


# ---------------------------------------------------------------------------
# Consent-gated routes redirect to /consent when unconsented
# ---------------------------------------------------------------------------


def test_stylists_redirect_unauthenticated(client):
    response = client.get("/stylists")
    assert response.status_code == 302
    assert "/login" in response.location


def test_style_studio_redirect_unauthenticated(client):
    response = client.get("/style-studio")
    assert response.status_code == 302
    assert "/login" in response.location


def test_style_studio_consented(auth_client, hairstyle):
    response = auth_client.get("/style-studio")
    assert response.status_code == 200
    assert b"Test Cut" in response.data or b"style" in response.data.lower()


def test_stylists_consented(auth_client, stylist):
    response = auth_client.get("/stylists")
    assert response.status_code == 200
    assert b"Jane Stylist" in response.data or b"stylist" in response.data.lower()
    # `stylist` fixture leaves `google_maps_url` null — the Maps pin should
    # not render. Guards against accidentally hardcoding the icon.
    assert b"bi-geo-alt" not in response.data


def test_stylists_renders_maps_icon_when_url_set(auth_client, app):
    with app.app_context():
        s = Stylist(
            name="Pinned Stylist",
            google_maps_url="https://maps.app.goo.gl/example",
        )
        db.session.add(s)
        db.session.commit()
    response = auth_client.get("/stylists")
    assert response.status_code == 200
    assert response.data.count(b"bi-geo-alt") == 1
    assert b"https://maps.app.goo.gl/example" in response.data


def test_stylists_search(auth_client, stylist):
    response = auth_client.get("/stylists?q=Jane")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dashboard + export: admin OAuth email-allowlist gating (issue #63).
# ---------------------------------------------------------------------------


def test_dashboard_redirects_to_login_when_unauthenticated(client):
    """Anonymous request to /dashboard -> redirect to /login."""
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.location


def test_dashboard_blocks_non_admin_user(auth_client):
    """A signed-in non-admin gets 403 + the admin_unauthorized page."""
    response = auth_client.get("/dashboard")
    assert response.status_code == 403
    assert b"Admin access required" in response.data


def test_dashboard_allowed_for_admin_user(admin_client):
    """An admin user lands on Operations via /dashboard -> /dashboard/operations."""
    response = admin_client.get("/dashboard")
    assert response.status_code == 302
    assert "/dashboard/operations" in response.location

    followed = admin_client.get("/dashboard", follow_redirects=True)
    assert followed.status_code == 200


def test_admin_user_does_not_need_session_id(app, admin_client):
    """An admin user with no session_id cookie can still access the dashboard and export."""
    with admin_client.session_transaction() as sess:
        assert "session_id" not in sess
    assert admin_client.get("/dashboard/operations").status_code == 200
    assert admin_client.get("/api/admin/export?format=json").status_code == 200


# -----------------------------------------------------------------------------
# Dashboard: /dashboard redirects to /dashboard/operations; experiment route gone
# -----------------------------------------------------------------------------


def test_dashboard_redirects_to_operations_for_admin(admin_client):
    """GET /dashboard redirects admins to Operations (the only remaining dashboard)."""
    response = admin_client.get("/dashboard")
    assert response.status_code == 302
    assert "/dashboard/operations" in response.location


def test_experiment_dashboard_returns_404(admin_client):
    """The Experiment dashboard route has been removed."""
    assert admin_client.get("/dashboard/experiment").status_code == 404


def test_operations_dashboard_renders_for_admin(admin_client):
    """Operations dashboard renders with 200 for allowlisted admin."""
    response = admin_client.get("/dashboard/operations")
    assert response.status_code == 200
    assert b"Operations" in response.data
    assert b"Today's Visits" in response.data


def test_operations_dashboard_blocks_unauthenticated(client):
    response = client.get("/dashboard/operations")
    assert response.status_code == 302
    assert "/login" in response.location


def test_operations_dashboard_does_not_include_export_buttons(admin_client):
    """Export remains accessible via /api/admin/export but isn't surfaced on the dashboard."""
    response = admin_client.get("/dashboard/operations")
    assert response.status_code == 200
    assert b"Experiment Data Export" not in response.data


def test_operations_dashboard_renders_ai_recommended_card(admin_client):
    """The Operations dashboard surfaces the AI-recommended selection rate metric."""
    response = admin_client.get("/dashboard/operations")
    assert response.status_code == 200
    assert b"AI-Recommended Rate" in response.data


def test_operations_dashboard_ai_rec_rate_with_data(app, admin_client, hairstyle):
    """AI-recommended rate is the share of generations where was_ai_recommended is True."""
    with app.app_context():
        # 3 known-context generations: 2 AI-recommended, 1 not. Plus 1 legacy null
        # row that should be excluded from the denominator.
        for was_ai in (True, True, False, None):
            db.session.add(
                GeneratedImage(
                    session_id=str(uuid.uuid4()),
                    hairstyle_id=hairstyle.id,
                    was_ai_recommended=was_ai,
                )
            )
        db.session.commit()

    response = admin_client.get("/dashboard/operations")
    assert response.status_code == 200
    # 2 / 3 = 66%
    assert b">66%<" in response.data


def test_admin_export_redirects_when_unauthenticated(client):
    response = client.get("/api/admin/export")
    assert response.status_code == 302
    assert "/login" in response.location


def test_admin_export_json(app, admin_client):
    _make_participant_data(app)
    response = admin_client.get("/api/admin/export?format=json")
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


def test_admin_export_csv(app, admin_client):
    _make_participant_data(app)
    response = admin_client.get("/api/admin/export")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]

    csv_data = response.data.decode("utf-8")
    assert "participant_id" in csv_data
    assert "experiment_group" in csv_data


def test_admin_export_one_row_per_participant(app, admin_client):
    """Export emits one row per unique session_id, not per ExperimentSession row."""
    _make_participant_data(app, experiment_group="control")
    _make_participant_data(app, experiment_group="experimental")
    response = admin_client.get("/api/admin/export?format=json")
    data = response.get_json()
    assert len(data) == 2


def test_admin_export_dedupes_timeout_resume_sessions(app, admin_client):
    """A participant with multiple ExperimentSession rows (timeout+resume) yields one export row.

    Images and ratings must not be double-counted; session_duration_seconds must
    be the sum across rows for that participant.
    """
    sid = str(uuid.uuid4())
    started = datetime.now(timezone.utc)

    with app.app_context():
        db.session.add(Consent(session_id=sid, experiment_group="control"))
        db.session.add(
            ExperimentSession(
                session_id=sid,
                experiment_group="control",
                started_at=started,
                last_ping_at=started,
                ended_at=started,
                duration_seconds=120,
            )
        )
        db.session.add(
            ExperimentSession(
                session_id=sid,
                experiment_group="control",
                started_at=started,
                last_ping_at=started,
                ended_at=started,
                duration_seconds=300,
            )
        )
        db.session.commit()

    response = admin_client.get("/api/admin/export?format=json")
    assert response.status_code == 200
    data = response.get_json()

    matching = [r for r in data if r["session_duration_seconds"] == 420]
    assert len(matching) == 1, f"expected one merged row, got {data}"
    assert matching[0]["experiment_group"] == "control"


def test_admin_export_invalid_format(admin_client):
    response = admin_client.get("/api/admin/export?format=xml")
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
# Session start / ping / end — endpoints removed; verify they 404
# ---------------------------------------------------------------------------


def test_api_session_endpoints_removed(auth_client):
    """The IRB heartbeat endpoints are gone; all three should 404 for an authenticated user."""
    assert auth_client.post("/api/session/start").status_code == 404
    assert (
        auth_client.post(
            "/api/session/ping",
            json={"session_id": "anything"},
            content_type="application/json",
        ).status_code
        == 404
    )
    assert (
        auth_client.post(
            "/api/session/end",
            json={"session_id": "anything"},
            content_type="application/json",
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# POST /api/recommend
# ---------------------------------------------------------------------------


def test_api_recommend_unauthenticated_returns_401(client):
    response = client.post(
        "/api/recommend",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 401


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
# was_ai_recommended flag on GeneratedImage (IRB primary metric)
# ---------------------------------------------------------------------------


def _mock_generate_client():
    """Build a mocked genai client whose generate_content returns a tiny PNG."""
    from PIL import Image

    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    mock_part = MagicMock()
    mock_part.inline_data = MagicMock(data=buf.getvalue(), mime_type="image/png")

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(parts=[mock_part])
    return mock_client


@patch("app.routes.main.get_genai_client")
def test_api_generate_sets_was_ai_recommended_null_for_control(
    mock_get_client, app, auth_client, hairstyle
):
    """Control-group sessions store was_ai_recommended as NULL (not applicable)."""
    mock_get_client.return_value = _mock_generate_client()

    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    gen_id = int(response.headers["X-Generated-Image-Id"])
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, gen_id)
        assert gen_img.was_ai_recommended is None


@patch("app.routes.main.get_genai_client")
def test_api_generate_sets_was_ai_recommended_true_when_style_was_recommended(
    mock_get_client, app, experimental_client, hairstyle
):
    """Experimental group + selected style in Recommendation rows → True."""
    from app.models import Recommendation

    client, sid = experimental_client
    with app.app_context():
        db.session.add(
            Recommendation(
                session_id=sid,
                hairstyle_id=hairstyle.id,
                reasoning="Suits your face shape.",
            )
        )
        db.session.commit()

    mock_get_client.return_value = _mock_generate_client()

    response = client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    gen_id = int(response.headers["X-Generated-Image-Id"])
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, gen_id)
        assert gen_img.was_ai_recommended is True


@patch("app.routes.main.get_genai_client")
def test_api_generate_sets_was_ai_recommended_false_when_style_not_recommended(
    mock_get_client, app, experimental_client, hairstyle
):
    """Experimental group + selected style absent from Recommendation rows → False."""
    from app.models import Hairstyle, Recommendation

    client, sid = experimental_client
    with app.app_context():
        other = Hairstyle(
            name="Other Cut",
            description="Not recommended here",
            category="MODERN",
            image_url="/static/other.png",
        )
        db.session.add(other)
        db.session.commit()
        db.session.add(
            Recommendation(
                session_id=sid,
                hairstyle_id=other.id,
                reasoning="A different suggestion.",
            )
        )
        db.session.commit()

    mock_get_client.return_value = _mock_generate_client()

    response = client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    gen_id = int(response.headers["X-Generated-Image-Id"])
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, gen_id)
        assert gen_img.was_ai_recommended is False


# ---------------------------------------------------------------------------
# Custom reference upload path (issue #97)
# ---------------------------------------------------------------------------


@patch("app.routes.main.get_genai_client")
def test_api_generate_with_reference_photo_records_custom_reference(
    mock_get_client, app, auth_client, hairstyle
):
    """A reference_photo upload generates an image with hairstyle_id NULL
    and used_custom_reference=True."""
    mock_get_client.return_value = _mock_generate_client()

    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "selfie.jpg"),
            "reference_photo": (make_test_image(), "inspiration.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    gen_id = int(response.headers["X-Generated-Image-Id"])
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, gen_id)
        assert gen_img.hairstyle_id is None
        assert gen_img.used_custom_reference is True
        assert gen_img.was_ai_recommended is None


@patch("app.routes.main.get_genai_client")
def test_api_generate_with_reference_photo_ignores_hairstyle_id(
    mock_get_client, app, auth_client, hairstyle
):
    """When reference_photo is present, hairstyle_id is ignored — catalog OR reference,
    not both. The row stores hairstyle_id=NULL even if the form submitted one."""
    mock_get_client.return_value = _mock_generate_client()

    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "selfie.jpg"),
            "reference_photo": (make_test_image(), "inspiration.jpg"),
            "hairstyle_id": str(hairstyle.id),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    gen_id = int(response.headers["X-Generated-Image-Id"])
    with app.app_context():
        gen_img = db.session.get(GeneratedImage, gen_id)
        assert gen_img.hairstyle_id is None
        assert gen_img.used_custom_reference is True


@patch("app.routes.main.get_genai_client")
def test_api_generate_with_reference_photo_passes_both_images_to_gemini(
    mock_get_client, app, auth_client
):
    """The Gemini call sees the user's selfie and the reference image, plus
    a prompt that targets the reference's hair (not a catalog name)."""
    mock_get_client.return_value = _mock_generate_client()

    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "selfie.jpg"),
            "reference_photo": (make_test_image(), "inspiration.jpg"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    call_kwargs = mock_get_client.return_value.models.generate_content.call_args.kwargs
    contents = call_kwargs["contents"]
    # prompt + selfie + reference
    assert len(contents) == 3
    prompt = contents[0]
    assert "reference image" in prompt.lower()


def test_api_generate_rejects_corrupted_reference_photo(auth_client):
    """A corrupted reference_photo is rejected before Gemini is called."""
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "selfie.jpg"),
            "reference_photo": (
                io.BytesIO(b"not-an-image"),
                "ref.jpg",
                "image/jpeg",
            ),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"Invalid or corrupted" in response.data


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


# ---------------------------------------------------------------------------
# POST /api/analyze-photo
# ---------------------------------------------------------------------------


def _mock_analyze_response(payload):
    """Build a mocked genai client whose generate_content returns `payload` as JSON."""
    import json as _json

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = _json.dumps(payload)
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def test_api_analyze_photo_unauthenticated_returns_401(client):
    response = client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 401


def test_api_analyze_photo_missing_photo(auth_client):
    response = auth_client.post(
        "/api/analyze-photo",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_no_gemini_client(mock_get_client, auth_client):
    mock_get_client.return_value = None
    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_success(mock_get_client, auth_client):
    mock_get_client.return_value = _mock_analyze_response(
        {
            "photo_validation_status": "ok",
            "hair_type": "Type 4C coily",
            "length": "medium",
            "thickness": "thick",
            "color": "dark brown",
            "notes": "natural texture, no chemical processing",
            "raw_observation": "Type 4C hair, medium length, dark brown, naturally curly.",
        }
    )

    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["photo_validation_status"] == "ok"
    assert data["raw_observation"].startswith("Type 4C")
    assert data["hair_type"] == "Type 4C coily"


@pytest.mark.parametrize(
    "status,expected_phrase",
    [
        ("no_face", b"face"),
        ("multiple_faces", b"more than one"),
        ("non_human", b"person"),
    ],
)
@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_rejects_bad_validation(
    mock_get_client, auth_client, status, expected_phrase
):
    mock_get_client.return_value = _mock_analyze_response(
        {
            "photo_validation_status": status,
            "hair_type": "",
            "length": "",
            "thickness": "",
            "color": "",
            "notes": "",
            "raw_observation": "",
        }
    )

    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body["photo_validation_status"] == status
    assert expected_phrase in response.data


@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_unknown_status_returns_500(mock_get_client, auth_client):
    mock_get_client.return_value = _mock_analyze_response(
        {
            "photo_validation_status": "blurry",
            "raw_observation": "",
        }
    )

    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_empty_observation_returns_500(mock_get_client, auth_client):
    """An 'ok' status with an empty observation is a server error, not a user error."""
    mock_get_client.return_value = _mock_analyze_response(
        {"photo_validation_status": "ok", "raw_observation": ""}
    )

    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_analyze_photo_truncates_oversized_observation(
    mock_get_client, auth_client
):
    """Gemini may overshoot MAX_OBSERVATION_LENGTH; we truncate so the next call doesn't 400."""
    from app.routes.main import MAX_OBSERVATION_LENGTH

    mock_get_client.return_value = _mock_analyze_response(
        {
            "photo_validation_status": "ok",
            "hair_type": "Type 1A",
            "length": "long",
            "thickness": "fine",
            "color": "blonde",
            "notes": "",
            "raw_observation": "X" * (MAX_OBSERVATION_LENGTH + 1000),
        }
    )

    response = auth_client.post(
        "/api/analyze-photo",
        data={"photo": (make_test_image(), "test.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["raw_observation"]) == MAX_OBSERVATION_LENGTH


# ---------------------------------------------------------------------------
# POST /api/refine-observation
# ---------------------------------------------------------------------------


def test_api_refine_observation_unauthenticated_returns_401(client):
    response = client.post(
        "/api/refine-observation",
        json={"original_observation": "Short hair", "user_edits": "Going grey"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"user_edits": "Going grey"},
        {"original_observation": "Short hair"},
        {"original_observation": "  ", "user_edits": "Going grey"},
        {"original_observation": "Short hair", "user_edits": "  "},
    ],
)
def test_api_refine_observation_missing_fields(auth_client, payload):
    response = auth_client.post("/api/refine-observation", json=payload)
    assert response.status_code == 400


def test_api_refine_observation_rejects_oversized_input(auth_client):
    response = auth_client.post(
        "/api/refine-observation",
        json={
            "original_observation": "A" * 4001,
            "user_edits": "Going grey",
        },
    )
    assert response.status_code == 400

    response = auth_client.post(
        "/api/refine-observation",
        json={
            "original_observation": "Short hair",
            "user_edits": "B" * 2001,
        },
    )
    assert response.status_code == 400


@patch("app.routes.main.get_genai_client")
def test_api_refine_observation_success(mock_get_client, auth_client):
    mock_get_client.return_value = _mock_analyze_response(
        {"raw_observation": "Type 4C hair, medium length, naturally grey."}
    )

    response = auth_client.post(
        "/api/refine-observation",
        json={
            "original_observation": "Type 4C hair, medium length, dark brown.",
            "user_edits": "My natural color is grey.",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "grey" in data["raw_observation"]


@patch("app.routes.main.get_genai_client")
def test_api_refine_observation_gemini_failure_returns_500(
    mock_get_client, auth_client
):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("API error")
    mock_get_client.return_value = mock_client

    response = auth_client.post(
        "/api/refine-observation",
        json={
            "original_observation": "Short hair",
            "user_edits": "Going grey",
        },
    )
    assert response.status_code == 500


@patch("app.routes.main.get_genai_client")
def test_api_refine_observation_truncates_oversized_observation(
    mock_get_client, auth_client
):
    """Same truncation guarantee as analyze."""
    from app.routes.main import MAX_OBSERVATION_LENGTH

    mock_get_client.return_value = _mock_analyze_response(
        {"raw_observation": "X" * (MAX_OBSERVATION_LENGTH + 500)}
    )

    response = auth_client.post(
        "/api/refine-observation",
        json={
            "original_observation": "Short hair",
            "user_edits": "Going grey",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["raw_observation"]) == MAX_OBSERVATION_LENGTH


# ---------------------------------------------------------------------------
# Observation propagation through /api/recommend and /api/generate
# ---------------------------------------------------------------------------


@patch("app.routes.main.get_genai_client")
def test_api_recommend_passes_observation_to_prompt(
    mock_get_client, app, experimental_client, hairstyle
):
    """Server should embed the observation form field into the Gemini prompt."""
    import json as _json

    client, _sid = experimental_client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = _json.dumps(
        {"recommendations": [{"hairstyle_id": hairstyle.id, "reasoning": "Suits you."}]}
    )
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    observation = "Type 4C hair, planning a hair transplant."
    response = client.post(
        "/api/recommend",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "observation": observation,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    prompt_text = call_kwargs["contents"][0]
    assert observation in prompt_text
    assert "authoritative" in prompt_text.lower()
    # Prompt-injection guard: observation must be presented as data, not instructions.
    assert "not instructions" in prompt_text.lower()


@patch("app.routes.main.get_genai_client")
def test_api_recommend_caps_at_four(mock_get_client, app, experimental_client):
    """Even if Gemini returns more than 4, only the first 4 are persisted/returned."""
    import json as _json
    from app.models import Hairstyle, Recommendation

    client, sid = experimental_client
    with app.app_context():
        for i in range(6):
            db.session.add(
                Hairstyle(
                    name=f"Cut {i}",
                    description=f"Style {i}",
                    category="MODERN",
                    image_url=f"/static/cut{i}.png",
                )
            )
        db.session.commit()
        all_styles = Hairstyle.query.all()

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = _json.dumps(
        {
            "recommendations": [
                {"hairstyle_id": h.id, "reasoning": f"Reason for {h.name}"}
                for h in all_styles
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
    assert len(data["recommendations"]) == 4

    with app.app_context():
        assert Recommendation.query.filter_by(session_id=sid).count() == 4


def test_api_recommend_rejects_oversized_observation(experimental_client):
    client, _sid = experimental_client
    response = client.post(
        "/api/recommend",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "observation": "A" * 4001,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


@patch("app.routes.main.get_genai_client")
def test_api_generate_passes_observation_to_prompt(
    mock_get_client, app, auth_client, hairstyle
):
    """Generate prompt should include the observation as authoritative."""
    mock_get_client.return_value = _mock_generate_client()

    observation = "Currently bald, planning a hair transplant."
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "hairstyle_id": str(hairstyle.id),
            "observation": observation,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200

    call_kwargs = mock_get_client.return_value.models.generate_content.call_args.kwargs
    prompt_text = call_kwargs["contents"][0]
    assert observation in prompt_text
    assert "authoritative" in prompt_text.lower()
    # Prompt-injection guard: observation must be presented as data, not instructions.
    assert "not instructions" in prompt_text.lower()


def test_api_generate_rejects_oversized_observation(auth_client, hairstyle):
    response = auth_client.post(
        "/api/generate",
        data={
            "photo": (make_test_image(), "test.jpg"),
            "hairstyle_id": str(hairstyle.id),
            "observation": "A" * 4001,
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /gallery + GET /api/me/storage-key (issue #106)
# ---------------------------------------------------------------------------


def test_gallery_unauthenticated_redirects_to_login(client):
    response = client.get("/gallery")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_gallery_authenticated_renders(auth_client):
    response = auth_client.get("/gallery")
    assert response.status_code == 200
    # The page is a thin shell — gallery.js does the heavy lifting client-side.
    assert b"gallery.js" in response.data


def test_storage_key_unauthenticated_returns_401(client):
    response = client.get("/api/me/storage-key")
    assert response.status_code == 401


def test_storage_key_returns_user_id_and_salt(auth_client, app):
    from app.models import User

    response = auth_client.get("/api/me/storage-key")
    assert response.status_code == 200
    data = response.get_json()
    assert "user_id" in data and "salt" in data

    with app.app_context():
        user = db.session.get(User, data["user_id"])
        assert user is not None
        assert user.email == "user@example.com"
        # Salt is server-issued and must match what the user was provisioned with.
        assert data["salt"] == user.storage_salt
        # Default salt is 32 random bytes hex-encoded → 64 chars.
        assert len(data["salt"]) == 64


def test_storage_key_is_stable_across_requests(auth_client):
    """Salt persists across calls so encrypted blobs remain decryptable."""
    first = auth_client.get("/api/me/storage-key").get_json()
    second = auth_client.get("/api/me/storage-key").get_json()
    assert first == second
