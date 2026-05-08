"""Tests for the database-backed server-side error logger (issue #17)."""

from unittest.mock import patch

from flask import Blueprint

from app.models import ErrorLog, db


def _register_test_routes(app):
    """Attach a fresh blueprint with a route that raises and a route that
    catches-and-logs. Done once per test so each test gets its own routes.
    """
    bp = Blueprint(f"errortest_{id(app)}", __name__)

    @bp.route("/__test/uncaught")
    def uncaught():
        raise RuntimeError("kaboom uncaught")

    @bp.route("/__test/caught")
    def caught():
        try:
            raise ValueError("kaboom caught")
        except ValueError:
            from flask import current_app

            current_app.logger.exception("handled value error")
            return "ok", 200

    @bp.route("/__test/log_no_exc")
    def log_no_exc():
        from flask import current_app

        current_app.logger.error("plain error message, no exc_info")
        return "ok", 200

    app.register_blueprint(bp)


def test_uncaught_exception_writes_error_log_row(app, client):
    _register_test_routes(app)
    app.config["TESTING"] = False  # let Flask invoke the error handler chain

    client.get("/__test/uncaught")

    with app.app_context():
        rows = ErrorLog.query.all()
        assert len(rows) == 1
        row = rows[0]
        assert row.route == "/__test/uncaught"
        assert row.method == "GET"
        assert row.exception_class == "RuntimeError"
        assert "kaboom uncaught" in (row.message or "") or "kaboom uncaught" in (
            row.traceback or ""
        )
        assert row.traceback is not None
        assert "RuntimeError" in row.traceback


def test_caught_exception_logged_via_logger_exception_writes_row(app, client):
    """Developer-handled errors that flash a message should still be logged
    when the developer calls current_app.logger.exception(...)."""
    _register_test_routes(app)

    response = client.get("/__test/caught")
    assert response.status_code == 200  # caught + flashed-style behavior

    with app.app_context():
        rows = ErrorLog.query.all()
        assert len(rows) == 1
        row = rows[0]
        assert row.route == "/__test/caught"
        assert row.exception_class == "ValueError"
        assert row.traceback is not None
        assert "ValueError" in row.traceback
        assert row.message == "handled value error"


def test_logger_error_without_exc_info_records_route_and_message(app, client):
    """Plain logger.error('foo') without exc_info still records route +
    message; traceback and exception_class are NULL."""
    _register_test_routes(app)

    client.get("/__test/log_no_exc")

    with app.app_context():
        rows = ErrorLog.query.all()
        assert len(rows) == 1
        row = rows[0]
        assert row.route == "/__test/log_no_exc"
        assert row.message == "plain error message, no exc_info"
        assert row.exception_class is None
        assert row.traceback is None


def test_db_failure_does_not_break_response(app, client):
    """If the DB write fails, the handler must swallow the failure so the
    response cycle isn't broken and we don't recurse."""
    _register_test_routes(app)
    app.config["TESTING"] = False

    real_commit = db.session.commit

    def _exploding_commit():
        # Roll back so the session can be reused after; then raise.
        db.session.rollback()
        raise RuntimeError("simulated DB outage")

    with patch.object(db.session, "commit", side_effect=_exploding_commit):
        # If the handler doesn't swallow, this call will raise out of the
        # test client and fail the test.
        response = client.get("/__test/uncaught")

    # 500 from the original RuntimeError, not from the logger
    assert response.status_code == 500

    # restore for any teardown that needs to commit
    db.session.commit = real_commit


def test_authenticated_user_id_is_recorded(app, admin_client):
    _register_test_routes(app)

    admin_client.get("/__test/caught")

    with app.app_context():
        row = ErrorLog.query.first()
        assert row is not None
        assert row.user_id is not None


def test_unauthenticated_user_id_is_null(app, client):
    _register_test_routes(app)

    client.get("/__test/caught")

    with app.app_context():
        row = ErrorLog.query.first()
        assert row is not None
        assert row.user_id is None


def test_request_body_fields_are_not_persisted(app, client):
    """Privacy hygiene: form data, JSON body, and uploaded files must never
    end up in any column. We don't read them in the handler — verify by
    posting sensitive-looking content and confirming none of it appears.
    """
    bp = Blueprint(f"privacytest_{id(app)}", __name__)

    @bp.route("/__test/sensitive", methods=["POST"])
    def sensitive():
        raise RuntimeError("boom")

    app.register_blueprint(bp)
    app.config["TESTING"] = False

    secret = "DO_NOT_LOG_THIS_PHOTO_BYTES_OR_FORM_VALUE_xyz123"
    client.post(
        "/__test/sensitive",
        data={"observation": secret, "secret_field": secret},
    )

    with app.app_context():
        row = ErrorLog.query.first()
        assert row is not None
        for field in (row.message, row.traceback, row.route, row.method):
            assert secret not in (field or ""), (
                f"sensitive value leaked into ErrorLog field: {field!r}"
            )


def test_warning_level_does_not_create_row(app, client):
    """Handler is set at ERROR level; warnings/info should be ignored."""
    bp = Blueprint(f"warntest_{id(app)}", __name__)

    @bp.route("/__test/warn")
    def warn():
        from flask import current_app

        current_app.logger.warning("just a warning")
        current_app.logger.info("just an info")
        return "ok", 200

    app.register_blueprint(bp)

    client.get("/__test/warn")

    with app.app_context():
        assert ErrorLog.query.count() == 0
