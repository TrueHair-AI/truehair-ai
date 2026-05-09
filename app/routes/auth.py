"""Consumer auth — Google OAuth for every TrueHair user.

Replaces the IRB-era anonymous `session_id` UUID and the admin-only OAuth
allowlist. After a successful Google sign-in, the User row is created (or
updated) and `session["user_id"]` is set; `is_admin` lives on the User row.
"""

from datetime import datetime, timezone

from flask import Blueprint, redirect, render_template, session, url_for
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import make_google_blueprint

from app.models import User, db
from app.services.session_identity import get_session_id, new_session_id

auth_bp = Blueprint("auth", __name__)
# After a successful OAuth callback, Flask-Dance hands control back here. The
# `oauth_authorized` signal below provisions the User row; `redirect_to` then
# sends the browser to the studio. Spec: always /style-studio post-login.
google_bp = make_google_blueprint(
    scope=["openid", "email", "profile"], redirect_to="main.style_studio"
)


@auth_bp.route("/login")
def login():
    """Render the login page; signed-in users skip straight to the studio."""
    if session.get("user_id"):
        return redirect(url_for("main.style_studio"))
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Sign out — clears `user_id` plus any leftover IRB-era session keys."""
    session.clear()
    return redirect(url_for("main.index"))


@oauth_authorized.connect_via(google_bp)
def _on_google_login(blueprint, token):
    """Create or update the User row after a successful Google sign-in.

    Returning False tells Flask-Dance not to persist the OAuth token — we
    only need it for the userinfo round-trip and the `session["user_id"]`
    assignment.
    """
    if not token:
        return False

    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return False

    info = resp.json()
    google_sub = info.get("id")
    email = (info.get("email") or "").lower()
    if not google_sub or not email:
        return False

    name = info.get("name")
    avatar = info.get("picture")
    now = datetime.now(timezone.utc)

    user = User.query.filter_by(google_sub=google_sub).first()

    if user is None:
        # Claim a pre-seeded admin row (created by the auth-foundation
        # migration) on first real sign-in: match by email when google_sub
        # is the placeholder `"pending:<email>"`.
        user = User.query.filter_by(email=email, google_sub=f"pending:{email}").first()
        if user is not None:
            user.google_sub = google_sub

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            display_name=name,
            avatar_url=avatar,
            terms_accepted_at=now,
        )
        db.session.add(user)
    else:
        # Refresh display fields each login so they track Google's record.
        user.display_name = name or user.display_name
        user.avatar_url = avatar or user.avatar_url

    user.last_login_at = now
    db.session.commit()

    session["user_id"] = user.id
    # GeneratedImage / Rating / Recommendation still have NOT NULL `session_id`
    # columns; mint one for this browser if it doesn't already carry one so
    # the four write paths in main.py succeed.
    if not get_session_id():
        new_session_id()
    return False
