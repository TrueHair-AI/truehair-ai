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