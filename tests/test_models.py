"""Tests for app models (repr and basic usage for coverage)."""

from app.models import (
    ExperimentSession,
    GeneratedImage,
    Rating,
    Visit,
    db,
)


def test_visit_repr(app, session_id):
    with app.app_context():
        v = Visit(page="Home", session_id=session_id)
        db.session.add(v)
        db.session.commit()
        assert "Home" in repr(v)
        assert str(v.id) in repr(v)


def test_hairstyle_repr(app, hairstyle):
    assert "Test Cut" in repr(hairstyle)


def test_stylist_repr(app, stylist):
    assert "Jane Stylist" in repr(stylist)


def test_generated_image_relationships(app, session_id, hairstyle):
    with app.app_context():
        gen = GeneratedImage(
            session_id=session_id,
            hairstyle_id=hairstyle.id,
        )
        db.session.add(gen)
        db.session.commit()

        assert gen.session_id == session_id
        assert gen.hairstyle_id == hairstyle.id


def test_generated_image_rating_relationship(app, session_id, hairstyle):
    """Rating is reachable as generated_image.rating (single object)."""
    with app.app_context():
        gen = GeneratedImage(
            session_id=session_id,
            hairstyle_id=hairstyle.id,
        )
        db.session.add(gen)
        db.session.commit()

        r = Rating(
            session_id=session_id,
            generated_image_id=gen.id,
            rating=4,
        )
        db.session.add(r)
        db.session.commit()

        db.session.refresh(gen)
        assert gen.rating is not None
        assert gen.rating.rating == 4


def test_experiment_session_lookup_by_session_id(app, session_id):
    """ExperimentSession is queryable by session_id (the primary identity key)."""
    with app.app_context():
        rows = ExperimentSession.query.filter_by(session_id=session_id).all()
        assert len(rows) == 1
        assert rows[0].experiment_group == "control"
