"""Admin OAuth gate — Google sign-in against an email allowlist.

Operational auth for the admin dashboard. Not part of the study protocol:
participants remain fully anonymous (see app/services/session_identity.py).
Admin identity lives in session["admin_email"], which is a separate key from
session["session_id"] and never joined to study data.
"""

from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    session,
    url_for,
)
from flask_dance.contrib.google import google, make_google_blueprint

ADMIN_EMAIL_KEY = "admin_email"

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
# redirect_to routes the post-OAuth hop back through admin.login so it can read
# userinfo, set session["admin_email"], and redirect to the dashboard. Without
# this, Flask-Dance falls back to "/" after a successful callback and a browser
# with a participant session_id cookie ends up on /style-studio.
google_bp = make_google_blueprint(scope=["email"], redirect_to="admin.login")


def _admin_allowlist():
    raw = current_app.config.get("ADMIN_EMAILS", "") or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def admin_required(f):
    """Allow the request only if session["admin_email"] is in the allowlist."""

    @wraps(f)
    def decorated(*args, **kwargs):
        email = (session.get(ADMIN_EMAIL_KEY) or "").lower()
        if email and email in _admin_allowlist():
            return f(*args, **kwargs)
        return redirect(url_for("admin.login"))

    return decorated


@admin_bp.route("/login")
def login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        abort(403)
    email = (resp.json().get("email") or "").lower()
    if email not in _admin_allowlist():
        return render_template("admin_unauthorized.html", email=email), 403
    session[ADMIN_EMAIL_KEY] = email
    return redirect(url_for("main.dashboard"))


@admin_bp.route("/logout")
def logout():
    session.pop(ADMIN_EMAIL_KEY, None)
    return redirect(url_for("main.index"))
