import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """A signed-in TrueHair user. Identity comes from Google OAuth."""

    id = db.Column(db.Integer, primary_key=True)
    google_sub = db.Column(db.String(255), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(255))
    avatar_url = db.Column(db.String(500))
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    terms_accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    storage_salt = db.Column(
        db.String(64), nullable=False, default=lambda: secrets.token_hex(32)
    )
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User id={self.id} email={self.email} is_admin={self.is_admin}>"


class Visit(db.Model):
    """Records a page visit for analytics."""

    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(200), nullable=False)
    session_id = db.Column(db.String(36), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    timestamp = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Visit id={self.id} page='{self.page}' timestamp={self.timestamp}>"


class ExperimentSession(db.Model):
    """Tracks a user's session during an A/B test or experiment."""

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    experiment_group = db.Column(db.String(20), nullable=False)
    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_ping_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)


class Hairstyle(db.Model):
    """Defines a hairstyle option available in the catalog."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    image_url = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Hairstyle {self.name}>"


class GeneratedImage(db.Model):
    """Records the event of a hairstyle visualization being generated."""

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    hairstyle_id = db.Column(db.Integer, db.ForeignKey("hairstyle.id"), nullable=True)
    was_ai_recommended = db.Column(db.Boolean, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    hairstyle = db.relationship(
        "Hairstyle", backref=db.backref("generations", lazy=True)
    )


class Rating(db.Model):
    """Records user ratings for generated images."""

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    generated_image_id = db.Column(
        db.Integer, db.ForeignKey("generated_image.id"), nullable=False, unique=True
    )
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    generated_image = db.relationship(
        "GeneratedImage",
        backref=db.backref("rating", uselist=False, lazy=True),
    )


class Consent(db.Model):
    """Records user consent for participation in experiments."""

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, unique=True)
    experiment_group = db.Column(db.String(20), nullable=False)
    consented_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Recommendation(db.Model):
    """Stores AI-generated hairstyle recommendations."""

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    hairstyle_id = db.Column(db.Integer, db.ForeignKey("hairstyle.id"), nullable=False)
    reasoning = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ErrorLog(db.Model):
    """Persistent record of a server-side error.

    Captures both uncaught exceptions (Flask logs them via app.logger before
    rendering 500) and exceptions that view code caught and logged via
    current_app.logger.error/.exception(). The DBErrorLogHandler writes one
    row per logger record at ERROR level or above.
    """

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    route = db.Column(db.String(255))
    method = db.Column(db.String(10))
    exception_class = db.Column(db.String(255))
    message = db.Column(db.Text)
    traceback = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)


class Stylist(db.Model):
    """Represents a stylist in the directory."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    website = db.Column(db.String(500))
    instagram = db.Column(db.String(255))
    email = db.Column(db.String(120))
    specialties = db.Column(db.String(255))
    image_url = db.Column(db.String(255))

    def __repr__(self):
        return f"<Stylist {self.name}>"
