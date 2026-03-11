"""Tests for app models (repr and basic usage for coverage)."""

from app.models import (
    GeneratedImage,
    Visit,
    db,
)


def test_user_repr(app, user):
    assert "testuser" in repr(user)


def test_visit_repr(app, user):
    with app.app_context():
        v = Visit(page="Home", user_id=user.id)
        db.session.add(v)
        db.session.commit()
        assert "Home" in repr(v)
        assert str(v.id) in repr(v)


def test_hairstyle_repr(app, hairstyle):
    assert "Test Cut" in repr(hairstyle)


def test_stylist_repr(app, stylist):
    assert "Jane Stylist" in repr(stylist)


def test_user_image_relationship(app, user, user_image):
    """User.images backref includes user_image."""
    with app.app_context():
        from app.models import User, db

        u = db.session.get(User, user.id)
        assert u is not None
        assert user_image.user_id == u.id
        assert any(img.id == user_image.id for img in u.images)


def test_generated_image_relationships(app, user, user_image, hairstyle):
    with app.app_context():
        gen = GeneratedImage(
            user_id=user.id,
            user_image_id=user_image.id,
            hairstyle_id=hairstyle.id,
            image_url="uploads/gen.png",
        )
        db.session.add(gen)
        db.session.commit()
        assert gen.user_id == user.id
        assert gen.hairstyle_id == hairstyle.id
