import os
import uuid
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
from werkzeug.utils import secure_filename

from app.models import GeneratedImage, Hairstyle, Stylist, User, UserImage, Visit, db

main_bp = Blueprint("main", __name__)


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
    return {"current_user": user}


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


@main_bp.route("/upload", methods=["POST"])
@login_required
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        static_folder = current_app.static_folder or ""
        upload_path = os.path.join(static_folder, "uploads", filename)
        file.save(upload_path)

        user_image = UserImage(
            user_id=session["user_id"], image_url=f"uploads/{filename}"
        )
        db.session.add(user_image)
        db.session.commit()

        return jsonify(
            {
                "status": "success",
                "image_url": f"/static/uploads/{filename}",
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

    return render_template("result.html", latest_gen=gen_img)


@main_bp.route("/gallery")
@login_required
def gallery():
    log_visit("My Gallery")
    images = (
        GeneratedImage.query.filter_by(user_id=session["user_id"])
        .order_by(GeneratedImage.created_at.desc())
        .all()
    )
    return render_template("gallery.html", images=images)


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
        static_folder = current_app.static_folder or ""
        img_path = os.path.join(static_folder, user_image.image_url)
        user_photo = Image.open(img_path)

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

        result_filename = f"gen_{uuid.uuid4()}.png"
        result_url = f"uploads/{result_filename}"
        static_folder = current_app.static_folder or ""
        result_path = os.path.join(static_folder, result_url)

        for part in response.parts:
            if part.inline_data is not None:
                generated_image = part.as_image()
                generated_image.save(result_path)
                break
        else:
            raise Exception("No image returned by the model.")

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
                "image_url": f"/static/{result_url}",
                "image_id": gen_img.id,
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        current_app.logger.error(f"Gemini generation failed: {e}")
        return jsonify({"error": "Internal server error. Please try again later."}), 500