import csv
import io
import random
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from google import genai
from google.genai import types
from PIL import Image
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.models import (
    Consent,
    ExperimentSession,
    GeneratedImage,
    Hairstyle,
    Rating,
    Recommendation,
    Stylist,
    UserImage,
    Visit,
    db,
)
from app.services import r2 as r2_service
from app.services.session_identity import (
    consent_required,
    get_session_id,
    new_session_id,
)

main_bp = Blueprint("main", __name__)


def _day_of_week(date_column):
    """Return a SQL expression for day of week (0=Sunday .. 6=Saturday) for the current DB dialect."""
    if db.engine.dialect.name == "postgresql":
        return func.extract("dow", date_column)
    return func.strftime("%w", date_column)


def get_genai_client():
    """Return a google.genai Client configured with the API key, or None."""
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


@main_bp.app_context_processor
def inject_experiment_group():
    sid = get_session_id()
    experiment_group = None
    if sid:
        exp = (
            ExperimentSession.query.filter_by(session_id=sid)
            .order_by(ExperimentSession.started_at.desc())
            .first()
        )
        if exp:
            experiment_group = exp.experiment_group
    return {"experiment_group": experiment_group}


def log_visit(page_name):
    visit = Visit(page=page_name, session_id=get_session_id())
    db.session.add(visit)
    db.session.commit()


@main_bp.route("/")
def index():
    log_visit("Home")
    sid = get_session_id()
    if sid and Consent.query.filter_by(session_id=sid).first():
        return redirect(url_for("main.style_studio"))
    return redirect(url_for("main.consent_page"))


# ---------------------------------------------------------------------------
# Consent (minimal PR1 stub — issue #4 replaces this with IRB-verbatim content)
# ---------------------------------------------------------------------------


@main_bp.route("/consent", methods=["GET"])
def consent_page():
    sid = get_session_id()
    if sid and Consent.query.filter_by(session_id=sid).first():
        return redirect(url_for("main.style_studio"))
    return render_template("consent.html")


@main_bp.route("/consent", methods=["POST"])
def submit_consent():
    sid = get_session_id() or new_session_id()

    existing = Consent.query.filter_by(session_id=sid).first()
    if existing:
        return redirect(url_for("main.style_studio"))

    group = random.choice(["control", "experimental"])

    consent = Consent(session_id=sid, full_name="", experiment_group=group)
    exp_session = ExperimentSession(
        session_id=sid,
        experiment_group=group,
        started_at=datetime.now(timezone.utc),
        last_ping_at=datetime.now(timezone.utc),
    )
    db.session.add_all([consent, exp_session])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

    return redirect(url_for("main.style_studio"))


# ---------------------------------------------------------------------------
# Study routes
# ---------------------------------------------------------------------------


@main_bp.route("/style-studio")
@consent_required
def style_studio():
    """Render the style studio where users can select hairstyles."""
    log_visit("Style Studio")
    hairstyles = Hairstyle.query.all()
    categories = sorted(
        list(
            set(
                (h.category.upper() if h.category else "UNCATEGORIZED")
                for h in hairstyles
            )
        )
    )
    return render_template(
        "style_studio.html", hairstyles=hairstyles, categories=categories
    )


@main_bp.route("/api/upload/presign", methods=["POST"])
@consent_required
def upload_presign():
    """Return a presigned PUT URL so the client can upload directly to R2."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "photo.jpg")
    content_type = data.get("content_type", "image/jpeg")

    if content_type not in r2_service.ALLOWED_CONTENT_TYPES:
        return jsonify({"error": f"Unsupported content type: {content_type}"}), 400

    upload_key = r2_service.make_upload_key(filename)
    put_url = r2_service.get_presigned_put_url(upload_key, content_type)

    return jsonify({"put_url": put_url, "upload_key": upload_key})


@main_bp.route("/api/upload/confirm", methods=["POST"])
@consent_required
def upload_confirm():
    """Confirm a client-side R2 upload and create the DB record."""
    data = request.get_json(silent=True) or {}
    upload_key = data.get("upload_key")

    if not upload_key or not upload_key.startswith("uploads/"):
        return jsonify({"error": "Invalid upload_key"}), 400

    user_image = UserImage(
        session_id=get_session_id(),
        image_url=upload_key,
    )
    db.session.add(user_image)
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "image_url": r2_service.get_display_url(upload_key),
            "image_id": user_image.id,
        }
    )


@main_bp.route("/stylists")
@consent_required
def stylists():
    """Render the directory of stylists, optionally filtered by search query."""
    log_visit("Stylist Directory")
    query = request.args.get("q", "").strip()

    if query:
        search_filter = f"%{query}%"
        stylists_list = Stylist.query.filter(
            db.or_(
                Stylist.name.ilike(search_filter),
                Stylist.specialties.ilike(search_filter),
            )
        ).all()
    else:
        stylists_list = Stylist.query.all()

    return render_template("stylists.html", stylists=stylists_list, search_query=query)


# ---------------------------------------------------------------------------
# Admin dashboard / export — ungated pending issue #16 (decision: drop or gate).
# Queries rewritten to use ExperimentSession/session_id instead of the removed User model.
# ---------------------------------------------------------------------------


@main_bp.route("/dashboard")
def dashboard():
    """Render the admin KPI dashboard with analytics metrics."""
    log_visit("KPI Dashboard")

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    visits_today = Visit.query.filter(Visit.timestamp >= today_start).count()
    last_week_today = today_start - timedelta(days=7)
    time_elapsed_today = now - today_start
    visits_last_week_until_now = Visit.query.filter(
        Visit.timestamp >= last_week_today,
        Visit.timestamp < last_week_today + time_elapsed_today,
    ).count()

    visit_change = 0
    if visits_last_week_until_now > 0:
        visit_change = (
            (visits_today - visits_last_week_until_now) / visits_last_week_until_now
        ) * 100
    elif visits_today > 0:
        visit_change = 100

    # Each consented participant gets one ExperimentSession row at consent time,
    # so started_at is our "participant joined at" signal.
    new_participants = ExperimentSession.query.filter(
        ExperimentSession.started_at >= week_ago
    ).count()
    new_participants_last_week = ExperimentSession.query.filter(
        ExperimentSession.started_at >= two_weeks_ago,
        ExperimentSession.started_at < week_ago,
    ).count()

    user_change = 0
    if new_participants_last_week > 0:
        user_change = (
            (new_participants - new_participants_last_week) / new_participants_last_week
        ) * 100
    elif new_participants > 0:
        user_change = 100

    total_participants = ExperimentSession.query.count()
    participants_before_this_week = total_participants - new_participants
    total_users_change = 0
    if participants_before_this_week > 0:
        total_users_change = (new_participants / participants_before_this_week) * 100
    elif total_participants > 0:
        total_users_change = 100

    activated_count = db.session.query(GeneratedImage.session_id).distinct().count()
    activation_rate = (
        int(activated_count / total_participants * 100) if total_participants > 0 else 0
    )

    activated_before_week_ago = (
        db.session.query(GeneratedImage.session_id)
        .filter(GeneratedImage.created_at < week_ago)
        .distinct()
        .count()
    )
    participants_before_week_ago = ExperimentSession.query.filter(
        ExperimentSession.started_at < week_ago
    ).count()
    activation_rate_last_week = (
        int(activated_before_week_ago / participants_before_week_ago * 100)
        if participants_before_week_ago > 0
        else 0
    )
    activation_change = activation_rate - activation_rate_last_week

    retained_count = (
        db.session.query(GeneratedImage.session_id)
        .group_by(GeneratedImage.session_id)
        .having(func.count(GeneratedImage.id) > 1)
        .count()
    )
    retention_rate = (
        int(retained_count / activated_count * 100) if activated_count > 0 else 0
    )

    retained_before_week_ago_query = (
        db.session.query(GeneratedImage.session_id)
        .filter(GeneratedImage.created_at < week_ago)
        .group_by(GeneratedImage.session_id)
        .having(func.count(GeneratedImage.id) > 1)
    )
    retained_before_week_ago_count = db.session.query(
        retained_before_week_ago_query.subquery()
    ).count()
    retention_rate_last_week = (
        int(retained_before_week_ago_count / activated_before_week_ago * 100)
        if activated_before_week_ago > 0
        else 0
    )
    retention_change = retention_rate - retention_rate_last_week

    this_week_gens = {str(i): 0 for i in range(7)}
    last_week_gens = {str(i): 0 for i in range(7)}

    day_of_week = _day_of_week(GeneratedImage.created_at).label("dow")
    tw_data = (
        db.session.query(day_of_week, func.count(GeneratedImage.id))
        .filter(GeneratedImage.created_at >= week_ago)
        .group_by("dow")
        .all()
    )
    for row in tw_data:
        if row[0] is not None:
            this_week_gens[str(int(float(row[0])))] = row[1]

    lw_data = (
        db.session.query(day_of_week, func.count(GeneratedImage.id))
        .filter(
            GeneratedImage.created_at >= two_weeks_ago,
            GeneratedImage.created_at < week_ago,
        )
        .group_by("dow")
        .all()
    )
    for row in lw_data:
        if row[0] is not None:
            last_week_gens[str(int(float(row[0])))] = row[1]

    day_indices = ["1", "2", "3", "4", "5", "6", "0"]
    this_week_arr = [this_week_gens[d] for d in day_indices]
    last_week_arr = [last_week_gens[d] for d in day_indices]

    today_dow = now.strftime("%w")
    today_gen_count = this_week_gens.get(today_dow, 0)

    vp_data = (
        db.session.query(Visit.page, func.count(Visit.id))
        .filter(Visit.timestamp >= today_start)
        .group_by(Visit.page)
        .all()
    )

    mapped_vp = {page: count for page, count in vp_data if page is not None}

    visit_labels = list(mapped_vp.keys())
    visit_data = list(mapped_vp.values())

    return render_template(
        "dashboard.html",
        visits_today=visits_today,
        visit_change=round(visit_change, 1),
        new_users=new_participants,
        user_change=round(user_change, 1),
        activation_rate=activation_rate,
        activation_change=activation_change,
        retention_rate=retention_rate,
        retention_change=retention_change,
        total_users=total_participants,
        total_users_change=round(total_users_change, 1),
        today_gen_count=today_gen_count,
        generations_this_week=this_week_arr,
        generations_last_week=last_week_arr,
        visit_labels=visit_labels,
        visit_data=visit_data,
    )


@main_bp.route("/api/admin/export")
def export_data():
    """Export anonymized experiment data. Iterates ExperimentSession (one row per consented participant)."""
    sessions = ExperimentSession.query.order_by(ExperimentSession.started_at).all()

    rows = []

    for i, sess in enumerate(sessions, 1):
        sid = sess.session_id
        gen_images = GeneratedImage.query.filter_by(session_id=sid).all()
        num_visualizations = len(gen_images)

        ratings = Rating.query.filter_by(session_id=sid).all()
        avg_rating = (
            round(sum(r.rating for r in ratings) / len(ratings), 2) if ratings else None
        )
        num_ratings = len(ratings)

        duration = sess.duration_seconds
        if duration is None and sess.last_ping_at and sess.started_at:
            duration = int((sess.last_ping_at - sess.started_at).total_seconds())

        consent = Consent.query.filter_by(session_id=sid).first()
        consented_at = consent.consented_at.isoformat() if consent else None

        styles = ", ".join(
            sorted({gi.hairstyle.name for gi in gen_images if gi.hairstyle})
        )

        rows.append(
            {
                "participant_id": i,
                "experiment_group": sess.experiment_group,
                "num_visualizations": num_visualizations,
                "avg_rating": avg_rating,
                "num_ratings": num_ratings,
                "session_duration_seconds": duration,
                "styles_selected": styles,
                "consented_at": consented_at,
            }
        )

    fmt = request.args.get("format", "csv").lower()

    if fmt not in ["json", "csv"]:
        return jsonify({"error": "Invalid format. Use 'json' or 'csv'."}), 400

    if fmt == "json":
        return jsonify(rows)

    output = io.StringIO()

    fieldnames = [
        "participant_id",
        "experiment_group",
        "num_visualizations",
        "avg_rating",
        "num_ratings",
        "session_duration_seconds",
        "styles_selected",
        "consented_at",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    if rows:
        writer.writerows(rows)

    response = current_app.response_class(
        output.getvalue(),
        mimetype="text/csv",
    )

    response.headers["Content-Disposition"] = "attachment; filename=experiment_data.csv"

    return response


@main_bp.route("/result")
@main_bp.route("/result/<int:image_id>")
@consent_required
def result(image_id=None):
    """Render the result of an AI hairstyle generation."""
    log_visit("Results Page")
    sid = get_session_id()
    if image_id:
        gen_img = (
            GeneratedImage.query.options(joinedload(GeneratedImage.rating))
            .filter_by(id=image_id)
            .first()
        )
        if not gen_img:
            abort(404)
        if gen_img.session_id != sid:
            abort(403)
    else:
        gen_img = (
            GeneratedImage.query.options(joinedload(GeneratedImage.rating))
            .filter_by(session_id=sid)
            .order_by(GeneratedImage.created_at.desc())
            .first()
        )

    image_display_url = (
        r2_service.get_display_url(gen_img.image_url) if gen_img else None
    )

    return render_template(
        "result.html", latest_gen=gen_img, image_display_url=image_display_url
    )


@main_bp.route("/gallery")
@consent_required
def gallery():
    """Render the user's gallery of past generated hairstyles."""
    log_visit("My Gallery")
    images = (
        GeneratedImage.query.options(joinedload(GeneratedImage.rating))
        .filter_by(session_id=get_session_id())
        .order_by(GeneratedImage.created_at.desc())
        .all()
    )

    display_urls = {img.id: r2_service.get_display_url(img.image_url) for img in images}

    return render_template("gallery.html", images=images, display_urls=display_urls)


@main_bp.route("/terms")
def terms():
    """Render the Terms of Service page."""
    return render_template("terms.html")


@main_bp.route("/privacy")
def privacy():
    """Render the Privacy Policy page."""
    return render_template("privacy.html")


@main_bp.route("/api/recommend", methods=["POST"])
@consent_required
def recommend():
    """Generate hairstyle recommendations for a user based on their image."""
    import json

    sid = get_session_id()
    exp = (
        ExperimentSession.query.filter_by(session_id=sid)
        .order_by(ExperimentSession.started_at.desc())
        .first()
    )
    if not exp or exp.experiment_group != "experimental":
        abort(403)

    data = request.json
    user_image_id = data.get("user_image_id")
    if not user_image_id:
        return jsonify({"error": "Missing user_image_id"}), 400

    user_image = db.session.get(UserImage, user_image_id)
    if not user_image:
        return jsonify({"error": "Invalid user_image_id"}), 400

    if user_image.session_id != sid:
        abort(403)

    client = get_genai_client()
    if not client:
        return jsonify({"error": "Internal server error. Please try again later."}), 500

    try:
        photo_bytes = r2_service.download_bytes(user_image.image_url)
        user_photo = Image.open(io.BytesIO(photo_bytes))

        hairstyles = Hairstyle.query.all()
        catalog_list = [
            {"id": h.id, "name": h.name, "description": h.description}
            for h in hairstyles
        ]
        json_catalog = json.dumps(catalog_list)

        prompt_text = f"""You are a professional hairstylist and image consultant. Analyze the person in this photo
and recommend the best matching hairstyles from the catalog below.

Consider:
- Face shape (oval, round, square, heart, oblong, diamond)
- Apparent hair texture and current hair characteristics
- Overall facial features and proportions

HAIRSTYLE CATALOG:
{json_catalog}

Recommend exactly 5 to 8 hairstyles from the catalog. For each recommendation, explain
specifically why this style would suit this person based on your visual analysis.

Respond with a JSON object in this exact format:
{{
  "recommendations": [
    {{
      "hairstyle_id": <int>,
      "reasoning": "<2-3 sentences explaining why this style suits this person>"
    }}
  ]
}}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text, user_photo],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        response_json = json.loads(response.text)
        recs = response_json.get("recommendations", [])

        hairstyle_dict = {h.id: h for h in hairstyles}

        valid_recommendations = []
        for rec in recs:
            h_id = rec.get("hairstyle_id")
            reasoning = rec.get("reasoning")
            if h_id in hairstyle_dict:
                h = hairstyle_dict[h_id]
                valid_recommendations.append(
                    {
                        "hairstyle_id": h.id,
                        "name": h.name,
                        "description": h.description,
                        "image_url": h.image_url,
                        "reasoning": reasoning,
                    }
                )

                db_rec = Recommendation(
                    session_id=sid,
                    user_image_id=user_image.id,
                    hairstyle_id=h.id,
                    reasoning=reasoning,
                )
                db.session.add(db_rec)

        if not valid_recommendations:
            raise Exception("No valid recommendations returned.")

        db.session.commit()

        return jsonify({"status": "success", "recommendations": valid_recommendations})

    except Exception as e:
        import traceback

        traceback.print_exc()
        current_app.logger.error(f"Gemini recommendation failed: {e}")
        return jsonify(
            {
                "error": "AI recommendation could not be generated. This session cannot proceed. Please try again later."
            }
        ), 500


@main_bp.route("/api/generate", methods=["POST"])
@consent_required
def generate():
    """Generate a new image with the selected hairstyle using Gemini."""
    sid = get_session_id()
    data = request.json
    user_image_id = data.get("user_image_id")
    hairstyle_id = data.get("hairstyle_id")
    reference_image_id = data.get("reference_image_id")

    if not user_image_id:
        return jsonify({"error": "Missing user photo"}), 400

    if not hairstyle_id and not reference_image_id:
        return jsonify({"error": "Select a hairstyle or upload a reference image"}), 400

    user_image = db.session.get(UserImage, user_image_id)
    if not user_image:
        return jsonify({"error": "Invalid selection"}), 400
    if user_image.session_id != sid:
        abort(403)

    hairstyle = db.session.get(Hairstyle, hairstyle_id) if hairstyle_id else None
    if hairstyle_id and not hairstyle:
        return jsonify({"error": "Invalid hairstyle"}), 400

    reference_image = None
    if reference_image_id:
        reference_image = db.session.get(UserImage, reference_image_id)
        if not reference_image:
            return jsonify({"error": "Invalid reference image"}), 400
        if reference_image.session_id != sid:
            abort(403)

    client = get_genai_client()
    if not client:
        return jsonify({"error": "Internal server error. Please try again later."}), 500

    try:
        photo_bytes = r2_service.download_bytes(user_image.image_url)
        user_photo = Image.open(io.BytesIO(photo_bytes))

        contents = []

        if reference_image and hairstyle:
            ref_bytes = r2_service.download_bytes(reference_image.image_url)
            ref_photo = Image.open(io.BytesIO(ref_bytes))
            prompt = (
                f"Edit this person's photo to give them a hairstyle matching "
                f"the reference image provided. The target style is '{hairstyle.name}': "
                f"{hairstyle.description}. "
                f"Use the reference image as the primary guide for the exact look. "
                f"Keep the person's face, skin tone, and body exactly the same. "
                f"Only change their hair. Return the edited photo."
            )
            contents = [prompt, user_photo, ref_photo]
        elif reference_image:
            ref_bytes = r2_service.download_bytes(reference_image.image_url)
            ref_photo = Image.open(io.BytesIO(ref_bytes))
            prompt = (
                "Edit this person's photo to give them the hairstyle shown in "
                "the reference image. Replicate the hair style, length, texture, "
                "and shape from the reference as closely as possible. "
                "Keep the person's face, skin tone, and body exactly the same. "
                "Only change their hair. Return the edited photo."
            )
            contents = [prompt, user_photo, ref_photo]
        else:
            prompt = (
                f"Edit this person's photo to give them a '{hairstyle.name}' hairstyle. "
                f"{hairstyle.description}. "
                f"Keep the person's face, skin tone, and body exactly the same. "
                f"Only change their hair to match the described style. "
                f"Return the edited photo."
            )
            contents = [prompt, user_photo]

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                http_options=types.HttpOptions(timeout=120000),
            ),
        )

        image_part = None
        for part in response.parts:
            if part.inline_data is not None:
                image_part = part
                break
        else:
            raise Exception("No image returned by the model.")

        result_key = r2_service.make_generated_key()
        image_bytes = image_part.inline_data.data

        gen_image_pil = Image.open(io.BytesIO(image_bytes))
        webp_io = io.BytesIO()
        gen_image_pil.save(webp_io, format="WEBP", lossless=True)
        webp_bytes = webp_io.getvalue()

        r2_service.upload_bytes(result_key, webp_bytes, "image/webp")
        result_url = result_key

        gen_img = GeneratedImage(
            session_id=sid,
            user_image_id=user_image.id,
            hairstyle_id=hairstyle.id if hairstyle else None,
            reference_image_id=reference_image.id if reference_image else None,
            image_url=result_url,
        )
        db.session.add(gen_img)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "image_url": r2_service.get_display_url(result_url),
                "image_id": gen_img.id,
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        current_app.logger.error(f"Gemini generation failed: {e}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500


@main_bp.route("/api/rate", methods=["POST"])
def api_rate():
    """Submit or update a rating for a generated image."""
    sid = get_session_id()
    if not sid:
        return jsonify({"error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    raw_gen_id = data.get("generated_image_id")
    raw_rating = data.get("rating")

    if raw_gen_id is None or raw_rating is None:
        return jsonify({"error": "Missing generated_image_id or rating"}), 400

    # fmt: off
    try:
        gen_id = int(raw_gen_id)
        rating_val = int(raw_rating)
    except (TypeError, ValueError):  # fmt: skip
        return jsonify({"error": "Invalid generated_image_id or rating"}), 400
    # fmt: on

    if rating_val < 1 or rating_val > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400

    gen_img = db.session.get(GeneratedImage, gen_id)
    if not gen_img:
        return jsonify({"error": "Generated image not found"}), 404

    if gen_img.session_id != sid:
        abort(403)

    try:
        existing = Rating.query.filter_by(generated_image_id=gen_id).first()
        if existing:
            existing.rating = rating_val
        else:
            db.session.add(
                Rating(
                    session_id=sid,
                    generated_image_id=gen_id,
                    rating=rating_val,
                )
            )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Rating.query.filter_by(generated_image_id=gen_id).first()
        if not existing:
            current_app.logger.exception(
                "Rating upsert failed for generated_image_id=%s", gen_id
            )
            return jsonify({"error": "Unable to save rating"}), 409

        existing.rating = rating_val
        db.session.commit()

    return jsonify({"status": "success", "rating": rating_val})


DEFAULT_SESSION_TIMEOUT_SECONDS = 300


@main_bp.route("/api/session/start", methods=["POST"])
@consent_required
def api_session_start():
    """Start or resume an experiment session."""
    sid = get_session_id()

    latest_consent = Consent.query.filter_by(session_id=sid).first()
    experiment_group = latest_consent.experiment_group if latest_consent else "unknown"

    active_session = (
        ExperimentSession.query.filter_by(session_id=sid, ended_at=None)
        .order_by(ExperimentSession.started_at.desc())
        .first()
    )

    now = datetime.now(timezone.utc)

    if active_session:
        last_ping_at = active_session.last_ping_at
        if last_ping_at and last_ping_at.tzinfo is None:
            last_ping_at = last_ping_at.replace(tzinfo=timezone.utc)

        started_at = active_session.started_at
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        timeout = current_app.config.get(
            "SESSION_TIMEOUT_SECONDS", DEFAULT_SESSION_TIMEOUT_SECONDS
        )
        if (now - last_ping_at).total_seconds() > timeout:
            active_session.ended_at = last_ping_at
            active_session.duration_seconds = int(
                (active_session.ended_at - started_at).total_seconds()
            )
            new_session = ExperimentSession(
                session_id=sid,
                experiment_group=experiment_group,
                started_at=now,
                last_ping_at=now,
            )
            db.session.add(new_session)
            db.session.commit()
            return jsonify({"session_id": new_session.id})
        else:
            return jsonify({"session_id": active_session.id})

    new_session = ExperimentSession(
        session_id=sid,
        experiment_group=experiment_group,
        started_at=now,
        last_ping_at=now,
    )
    db.session.add(new_session)
    db.session.commit()
    return jsonify({"session_id": new_session.id})


@main_bp.route("/api/session/ping", methods=["POST"])
@consent_required
def api_session_ping():
    """Ping an active experiment session to keep it alive."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    exp_session = db.session.get(ExperimentSession, session_id)
    if not exp_session or exp_session.session_id != get_session_id():
        return jsonify({"error": "Session not found or forbidden"}), 404

    if exp_session.ended_at is not None:
        return jsonify({"error": "Session already ended"}), 400

    now = datetime.now(timezone.utc)
    exp_session.last_ping_at = now
    db.session.commit()

    return jsonify({"status": "ok"})


@main_bp.route("/api/session/end", methods=["POST"])
def api_session_end():
    """End an active experiment session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    exp_session = db.session.get(ExperimentSession, session_id)
    if not exp_session:
        return jsonify({"error": "Session not found"}), 404

    sid = get_session_id()
    if not sid or exp_session.session_id != sid:
        return jsonify({"error": "Forbidden"}), 403

    if exp_session.ended_at is None:
        now = datetime.now(timezone.utc)

        started_at = exp_session.started_at
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        exp_session.ended_at = now
        exp_session.duration_seconds = int((now - started_at).total_seconds())
        db.session.commit()

    return jsonify({"status": "success"})
