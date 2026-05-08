"""Database-backed error logger.

Persists server-side errors to the `error_log` table so they outlive Heroku's
~1-week log retention. Implemented as a `logging.Handler` subclass attached to
`app.logger` — captures both uncaught exceptions (Flask routes them through
`app.log_exception()` -> `app.logger.error(..., exc_info=True)`) and view-caught
exceptions where the developer called `current_app.logger.error/.exception(...)`.

Privacy: this module never reads `request.files`, `request.data`,
`request.form`, `request.get_json()`, or any other request body. Only the
route path, HTTP method, exception class, the formatted log message, and the
traceback string are persisted. `traceback.format_exc()` does not include
local variable values, so user input is not captured through that channel.
"""

import logging
import traceback as tb_module

from flask import has_request_context, request, session


class DBErrorLogHandler(logging.Handler):
    """Logging handler that writes ERROR-level records to the `error_log` table.

    Holds a reference to the app so we can open an app context for the DB
    write (the handler may fire from places like teardown handlers where the
    request context is unwinding).
    """

    def __init__(self, app, level=logging.ERROR):
        super().__init__(level=level)
        self.app = app

    def emit(self, record):
        """Write one log record as an `ErrorLog` row.

        Errors during the write are swallowed — a failing logger must never
        break the response cycle or trigger recursive logging.
        """
        try:
            self._write_row(record)
        except Exception:
            # Last-resort: print to stderr via logging.Handler.handleError so
            # we don't recurse through our own handler.
            self.handleError(record)

    def _write_row(self, record):
        from app.models import ErrorLog, db

        route, method, user_id = self._request_context_fields()
        exc_class, tb_text = self._exception_fields(record)

        entry = ErrorLog(
            route=route,
            method=method,
            exception_class=exc_class,
            message=record.getMessage(),
            traceback=tb_text,
            user_id=user_id,
        )

        # Use a fresh app context so the handler is safe to fire even when
        # the originating request context is mid-teardown.
        with self.app.app_context():
            try:
                db.session.add(entry)
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

    @staticmethod
    def _request_context_fields():
        """Return (route, method, user_id) from the current request, if any."""
        if not has_request_context():
            return None, None, None
        route = request.path
        method = request.method
        user_id = None
        try:
            user_id = session.get("user_id")
        except Exception:
            user_id = None
        return route, method, user_id

    @staticmethod
    def _exception_fields(record):
        """Return (exception_class, traceback_text) from a log record.

        Both fields are best-effort: handled errors logged without
        `exc_info=True` will have neither; uncaught exceptions and
        `logger.exception(...)` calls will have both.
        """
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            exc_class = exc_type.__name__ if exc_type else None
            tb_text = "".join(tb_module.format_exception(exc_type, exc_value, exc_tb))
            return exc_class, tb_text
        return None, None


def install_error_logging(app):
    """Attach the DB error log handler to `app.logger`."""
    handler = DBErrorLogHandler(app)
    app.logger.addHandler(handler)
