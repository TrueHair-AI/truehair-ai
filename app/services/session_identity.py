"""Per-browser session identity used to scope GeneratedImage / Rating /
Recommendation rows back to the request that produced them.

The cookie is minted in the OAuth callback (`auth.py`) so every signed-in
user has one for the lifetime of the login. The four write paths in
`main.py` (generate / rate / recommend / refine) read it to tie new rows
to the originating browser, which keeps cross-session isolation working
even when two accounts share a User row (e.g. shared family device).
"""

import uuid

from flask import session

SESSION_ID_KEY = "session_id"


def get_session_id():
    """Return the session UUID for this browser, or None if not yet minted."""
    return session.get(SESSION_ID_KEY)


def new_session_id():
    """Generate a new session UUID and store it in the signed session cookie."""
    sid = str(uuid.uuid4())
    session[SESSION_ID_KEY] = sid
    session.permanent = True
    return sid


def clear_session_id():
    """Remove the session identifier (used on logout)."""
    session.pop(SESSION_ID_KEY, None)
