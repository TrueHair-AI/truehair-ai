from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    profile_picture = db.Column(db.String(255))
    is_admin = db.Column(db.Boolean, default=False)
    experiment_group = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username}>"


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("visits", lazy=True))

    def __repr__(self):
        return f"<Visit id={self.id} page='{self.page}' timestamp={self.timestamp}>"


class ExperimentSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    experiment_group = db.Column(db.String(20), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_ping_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)  # NULL means session is still active
    duration_seconds = db.Column(db.Integer, nullable=True)  # Computed when session ends

    user = db.relationship("User", backref=db.backref("experiment_sessions", lazy=True))


class Hairstyle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # CLASSIC, MODERN, etc.
    image_url = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Hairstyle {self.name}>"


class UserImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("images", lazy=True))


class GeneratedImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user_image_id = db.Column(
        db.Integer, db.ForeignKey("user_image.id"), nullable=False
    )
    hairstyle_id = db.Column(db.Integer, db.ForeignKey("hairstyle.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("generated_images", lazy=True))
    user_image = db.relationship(
        "UserImage", backref=db.backref("generations", lazy=True)
    )
    hairstyle = db.relationship(
        "Hairstyle", backref=db.backref("generations", lazy=True)
    )


class Rating(db.Model):
    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    generated_image_id = db.Column(
        db.Integer, db.ForeignKey("generated_image.id"), nullable=False, unique=True
    )
    rating = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("ratings", lazy=True))
    generated_image = db.relationship(
        "GeneratedImage",
        backref=db.backref("rating", uselist=False, lazy=True),
    )


class Stylist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    website = db.Column(db.String(500))  # URLs with query params can exceed 255
    instagram = db.Column(db.String(255))
    email = db.Column(db.String(120))
    specialties = db.Column(db.String(255))  # Comma-separated list
    image_url = db.Column(db.String(255))

    def __repr__(self):
        return f"<Stylist {self.name}>"
