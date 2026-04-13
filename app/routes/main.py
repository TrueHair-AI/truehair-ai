import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from google import genai
from google.genai import types
from PIL import Image
from sqlalchemy import func

from app.models import GeneratedImage, Hairstyle, Stylist, User, UserImage, Visit, db
from app.services import r2 as r2_service

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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        user = db.session.get(User, session["user_id"])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


@main_bp.app_context_processor
def inject_user():
    user = None
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
    return {
        "current_user": user,
        "experiment_group": session.get("experiment_group"),
    }


def log_visit(page_name):
    user_id = session.get("user_id")
    visit = Visit(page=page_name, user_id=user_id)
    db.session.add(visit)
    db.session.commit()


@main_bp.route("/style-studio")
@login_required
def style_studio():
    log_visit("Style Studio")
    hairstyles = Hairstyle.query.all()
    return render_template("style_studio.html", hairstyles=hairstyles)


@main_bp.route("/api/upload/presign", methods=["POST"])
@login_required
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
@login_required
def upload_confirm():
    """Confirm a client-side R2 upload and create the DB record."""
    data = request.get_json(silent=True) or {}
    upload_key = data.get("upload_key")

    if not upload_key or not upload_key.startswith("uploads/"):
        return jsonify({"error": "Invalid upload_key"}), 400

    user_image = UserImage(
        user_id=session["user_id"],
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
@login_required
def stylists():
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


@main_bp.route("/dashboard")
@admin_required
def dashboard():
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

    new_users = User.query.filter(User.created_at >= week_ago).count()
    new_users_last_week = User.query.filter(
        User.created_at >= two_weeks_ago, User.created_at < week_ago
    ).count()

    user_change = 0
    if new_users_last_week > 0:
        user_change = ((new_users - new_users_last_week) / new_users_last_week) * 100
    elif new_users > 0:
        user_change = 100

    total_users = User.query.count()
    users_before_this_week = total_users - new_users
    total_users_change = 0
    if users_before_this_week > 0:
        total_users_change = (new_users / users_before_this_week) * 100
    elif total_users > 0:
        total_users_change = 100

    activated_users_count = db.session.query(GeneratedImage.user_id).distinct().count()
    activation_rate = (
        int(activated_users_count / total_users * 100) if total_users > 0 else 0
    )

    # Activation Rate Trend (based on state 7 days ago)
    activated_before_week_ago = (
        db.session.query(GeneratedImage.user_id)
        .filter(GeneratedImage.created_at < week_ago)
        .distinct()
        .count()
    )
    users_before_week_ago = User.query.filter(User.created_at < week_ago).count()
    activation_rate_last_week = (
        int(activated_before_week_ago / users_before_week_ago * 100)
        if users_before_week_ago > 0
        else 0
    )
    activation_change = activation_rate - activation_rate_last_week

    retained_users_count = (
        db.session.query(GeneratedImage.user_id)
        .group_by(GeneratedImage.user_id)
        .having(func.count(GeneratedImage.id) > 1)
        .count()
    )
    retention_rate = (
        int(retained_users_count / activated_users_count * 100)
        if activated_users_count > 0
        else 0
    )

    # Retention Rate Trend (based on state 7 days ago)
    retained_before_week_ago_query = (
        db.session.query(GeneratedImage.user_id)
        .filter(GeneratedImage.created_at < week_ago)
        .group_by(GeneratedImage.user_id)
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
        new_users=new_users,
        user_change=round(user_change, 1),
        activation_rate=activation_rate,
        activation_change=activation_change,
        retention_rate=retention_rate,
        retention_change=retention_change,
        total_users=total_users,
        total_users_change=round(total_users_change, 1),
        today_gen_count=today_gen_count,
        generations_this_week=this_week_arr,
        generations_last_week=last_week_arr,
        visit_labels=visit_labels,
        visit_data=visit_data,
    )


@main_bp.route("/api/admin/export")
@admin_required
def export_data():
    """Admin endpoint to export experiment data (basic version)."""

    users = User.query.filter(User.experiment_group.isnot(None)).all()

    rows = []

    for i, user in enumerate(users, 1):
        # Get all generated images for this user
        gen_images = GeneratedImage.query.filter_by(user_id=user.id).all()

        # Count visualizations
        num_visualizations = len(gen_images)

        # Get unique styles
        styles = ", ".join(set(gi.hairstyle.name for gi in gen_images if gi.hairstyle))

        rows.append(
            {
                "participant_id": i,
                "experiment_group": user.experiment_group,
                "num_visualizations": num_visualizations,
                "avg_rating": None,
                "num_ratings": 0,
                "session_duration_seconds": None,
                "styles_selected": styles,
                "consented_at": None,
            }
        )

    fmt = request.args.get("format", "csv")

    if fmt == "json":
        return jsonify(rows)

    output = io.StringIO()

    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    response = current_app.response_class(
        output.getvalue(),
        mimetype="text/csv",
    )

    response.headers["Content-Disposition"] = "attachment; filename=experiment_data.csv"

    return response


@main_bp.route("/result")
@main_bp.route("/result/<int:image_id>")
@login_required
def result(image_id=None):
    log_visit("Results Page")
    if image_id:
        gen_img = db.session.get(GeneratedImage, image_id)
        if not gen_img:
            abort(404)
        if gen_img.user_id != session["user_id"]:
            abort(403)
    else:
        gen_img = (
            GeneratedImage.query.filter_by(user_id=session["user_id"])
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
@login_required
def gallery():
    log_visit("My Gallery")
    images = (
        GeneratedImage.query.filter_by(user_id=session["user_id"])
        .order_by(GeneratedImage.created_at.desc())
        .all()
    )

    display_urls = {img.id: r2_service.get_display_url(img.image_url) for img in images}

    return render_template("gallery.html", images=images, display_urls=display_urls)


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/api/generate", methods=["POST"])
@login_required
def generate():
    data = request.json
    user_image_id = data.get("user_image_id")
    hairstyle_id = data.get("hairstyle_id")

    if not user_image_id or not hairstyle_id:
        return jsonify({"error": "Missing image or hairstyle selection"}), 400

    user_image = db.session.get(UserImage, user_image_id)
    hairstyle = db.session.get(Hairstyle, hairstyle_id)

    if not user_image or not hairstyle:
        return jsonify({"error": "Invalid selection"}), 400

    if not user_image.user_id == session["user_id"]:
        abort(403)

    client = get_genai_client()
    if not client:
        return jsonify({"error": "Internal server error. Please try again later."}), 500

    try:
        photo_bytes = r2_service.download_bytes(user_image.image_url)
        user_photo = Image.open(io.BytesIO(photo_bytes))

        prompt = (
            f"Edit this person's photo to give them a '{hairstyle.name}' hairstyle. "
            f"{hairstyle.description}. "
            f"Keep the person's face, skin tone, and body exactly the same. "
            f"Only change their hair to match the described style. "
            f"Return the edited photo."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, user_photo],
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

        # Transcode to lossless WebP
        gen_image_pil = Image.open(io.BytesIO(image_bytes))
        webp_io = io.BytesIO()
        gen_image_pil.save(webp_io, format="WEBP", lossless=True)
        webp_bytes = webp_io.getvalue()

        r2_service.upload_bytes(result_key, webp_bytes, "image/webp")
        result_url = result_key

        gen_img = GeneratedImage(
            user_id=session["user_id"],
            user_image_id=user_image.id,
            hairstyle_id=hairstyle.id,
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
