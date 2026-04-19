"""Anonymous session identity — IRB-compliant replacement for Google OAuth.

Each consented participant gets a UUIDv4 stored in Flask's signed session cookie.
No PII, no account, no login. See the approved IRB protocol (Sections 2.1, 6.5).
"""

import uuid
from functools import wraps

from flask import redirect, session, url_for

SESSION_ID_KEY = "session_id"


def get_session_id():
    """Return the anonymous session UUID for this browser, or None if not yet consented."""
    return session.get(SESSION_ID_KEY)


def new_session_id():
    """Generate a new anonymous session UUID and store it in the signed session cookie."""
    sid = str(uuid.uuid4())
    session[SESSION_ID_KEY] = sid
    session.permanent = True
    return sid


def clear_session_id():
    """Remove the session identifier (used if a participant actively abandons)."""
    session.pop(SESSION_ID_KEY, None)


def consent_required(f):
    """Gate access: participant must have clicked 'I agree' on the consent page."""
    from app.models import Consent

    @wraps(f)
    def decorated(*args, **kwargs):
        sid = get_session_id()
        if not sid:
            return redirect(url_for("main.consent_page"))
        if not Consent.query.filter_by(session_id=sid).first():
            return redirect(url_for("main.consent_page"))
        return f(*args, **kwargs)

    return decorated
