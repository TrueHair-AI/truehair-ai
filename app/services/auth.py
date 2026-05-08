"""Auth helpers — `current_user`, `login_required`, `admin_required`.

Identity comes from `session["user_id"]`, set in `app/routes/auth.py`'s
OAuth callback. See [SPRINT_6_ISSUES §S1](docs/sprint-6.md) for context.
"""

from functools import wraps

from flask import jsonify, redirect, render_template, request, session, url_for

from app.models import User, db


def current_user():
    """Return the signed-in `User` row, or None if no one is signed in."""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)


def login_required(f):
    """Gate a route on a signed-in user.

    HTML routes redirect to `/login`; `/api/*` routes return a 401 JSON body
    so the studio's `fetch()` calls handle auth failure cleanly.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """Gate a route on `User.is_admin`.

    Unauthenticated requests redirect to `/login`. Authenticated non-admins
    get the `admin_unauthorized.html` page with a 403.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("auth.login"))
        if not user.is_admin:
            return render_template("admin_unauthorized.html", email=user.email), 403
        return f(*args, **kwargs)

    return decorated
