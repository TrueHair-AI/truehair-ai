from flask import (
    Blueprint,
    redirect,
    render_template,
    session,
    url_for,
)
import random

from app.models import User, Visit, db

auth_bp = Blueprint("auth", __name__)


def log_visit(page_name):
    user_id = session.get("user_id")
    visit = Visit(page=page_name, user_id=user_id)
    db.session.add(visit)
    db.session.commit()


@auth_bp.route("/")
def login():
    log_visit("Home")
    if "user_id" in session:
        return redirect(url_for("main.style_studio"))
    return render_template("login.html")


@auth_bp.route("/login/google")
def google_login():
    from app import oauth

    google = oauth.google
    redirect_uri = url_for("auth.auth_google", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google")
def auth_google():
    from app import oauth

    google = oauth.google
    token = google.authorize_access_token()
    user_info = token.get("userinfo")

    if not user_info:
        return "Failed to fetch user info", 400

    email = user_info.get("email")
    user = User.query.filter_by(email=email).first()

    if not user:
        username = email.split("@")[0]
        base_username = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            first_name=user_info.get("given_name", ""),
            last_name=user_info.get("family_name", ""),
            profile_picture=user_info.get("picture", ""),
            experiment_group=random.choice(["control", "experimental"]),  
        )
        db.session.add(user)
        db.session.commit()

    elif user.experiment_group is None:
        user.experiment_group = random.choice(["control", "experimental"])
        db.session.commit()

    session["user_id"] = user.id
    session["experiment_group"] = user.experiment_group  

    return redirect(url_for("main.style_studio"))


@auth_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("experiment_group", None)
    return redirect(url_for("auth.login"))
