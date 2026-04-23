"""Tests for the _experiment_metrics() aggregation helper used by the Experiment dashboard."""

import uuid
from datetime import datetime, timezone

from app.models import (
    Consent,
    ExperimentSession,
    GeneratedImage,
    Rating,
    db,
)
from app.routes.main import _experiment_metrics


def _make_participant(
    group, hairstyle_id, ratings=None, n_viz=0, n_ai_rec=0, duration_seconds=None
):
    """Create a fully-formed participant row set. Returns the session_id."""
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.session.add(Consent(session_id=sid, experiment_group=group))
    db.session.add(
        ExperimentSession(
            session_id=sid,
            experiment_group=group,
            started_at=now,
            last_ping_at=now,
            ended_at=now,
            duration_seconds=duration_seconds,
        )
    )

    for i in range(n_viz):
        gi = GeneratedImage(
            session_id=sid,
            hairstyle_id=hairstyle_id,
            was_ai_recommended=(i < n_ai_rec) if group == "experimental" else None,
        )
        db.session.add(gi)
        db.session.flush()
        if ratings and i < len(ratings):
            db.session.add(
                Rating(
                    session_id=sid,
                    generated_image_id=gi.id,
                    rating=ratings[i],
                )
            )

    db.session.commit()
    return sid


def test_experiment_metrics_empty_db(app):
    """With no data, all aggregates are zero or None."""
    with app.app_context():
        m = _experiment_metrics()
        assert m["n_total"] == 0
        assert m["n_control"] == 0
        assert m["n_experimental"] == 0
        assert m["rating_stats"]["control"]["n"] == 0
        assert m["rating_stats"]["experimental"]["n"] == 0
        assert m["rating_stats"]["control"]["mean"] is None
        assert m["ai_rec_stats"]["n"] == 0
        assert sum(m["rating_hist"]["control"]) == 0
        assert sum(m["rating_hist"]["experimental"]) == 0


def test_experiment_metrics_basic_split(app, hairstyle):
    """Two participants in each group with realistic data produce correct per-group aggregates."""
    with app.app_context():
        _make_participant(
            "control", hairstyle.id, ratings=[3, 4], n_viz=2, duration_seconds=300
        )
        _make_participant(
            "control", hairstyle.id, ratings=[5], n_viz=1, duration_seconds=120
        )
        _make_participant(
            "experimental",
            hairstyle.id,
            ratings=[5, 5, 4],
            n_viz=3,
            n_ai_rec=2,
            duration_seconds=600,
        )
        _make_participant(
            "experimental",
            hairstyle.id,
            ratings=[4],
            n_viz=1,
            n_ai_rec=1,
            duration_seconds=240,
        )

        m = _experiment_metrics()

        assert m["n_control"] == 2
        assert m["n_experimental"] == 2
        assert m["n_total"] == 4

        assert m["rating_stats"]["control"]["n"] == 2
        assert m["rating_stats"]["control"]["mean"] == 4.25
        assert m["rating_stats"]["experimental"]["n"] == 2
        assert abs(m["rating_stats"]["experimental"]["mean"] - 4.33) < 0.01

        assert m["viz_stats"]["control"]["mean"] == 1.5
        assert m["viz_stats"]["experimental"]["mean"] == 2.0

        assert m["duration_stats"]["control"]["mean"] == 210.0
        assert m["duration_stats"]["experimental"]["mean"] == 420.0

        assert m["ai_rec_stats"]["n"] == 2
        assert abs(m["ai_rec_stats"]["mean"] - 0.83) < 0.01


def test_experiment_metrics_excludes_zero_rating_participants_from_rating_dist(
    app, hairstyle
):
    """Participants with zero ratings are not in the rating distribution, but are counted in completeness."""
    with app.app_context():
        _make_participant(
            "experimental", hairstyle.id, ratings=None, n_viz=0, duration_seconds=60
        )
        _make_participant(
            "experimental",
            hairstyle.id,
            ratings=[5],
            n_viz=1,
            n_ai_rec=1,
            duration_seconds=120,
        )

        m = _experiment_metrics()

        assert m["rating_stats"]["experimental"]["n"] == 1
        assert m["completeness"]["zero_viz"]["experimental"] == 1
        assert m["completeness"]["zero_rating"]["experimental"] == 1
        assert m["viz_stats"]["experimental"]["n"] == 2


def test_experiment_metrics_deduplicates_timeout_resume(app, hairstyle):
    """A participant with two ExperimentSession rows (timeout+resume) counts once; durations sum."""
    with app.app_context():
        sid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.session.add(Consent(session_id=sid, experiment_group="control"))
        db.session.add_all(
            [
                ExperimentSession(
                    session_id=sid,
                    experiment_group="control",
                    started_at=now,
                    last_ping_at=now,
                    ended_at=now,
                    duration_seconds=100,
                ),
                ExperimentSession(
                    session_id=sid,
                    experiment_group="control",
                    started_at=now,
                    last_ping_at=now,
                    ended_at=now,
                    duration_seconds=200,
                ),
            ]
        )
        db.session.commit()

        m = _experiment_metrics()

        assert m["n_control"] == 1
        assert m["duration_stats"]["control"]["mean"] == 300.0


def test_experiment_metrics_rating_histogram_bins(app, hairstyle):
    """Rating histogram correctly bins per-participant means."""
    with app.app_context():
        _make_participant(
            "control", hairstyle.id, ratings=[1], n_viz=1, duration_seconds=60
        )
        _make_participant(
            "control", hairstyle.id, ratings=[2], n_viz=1, duration_seconds=60
        )
        _make_participant(
            "control", hairstyle.id, ratings=[3], n_viz=1, duration_seconds=60
        )
        _make_participant(
            "control", hairstyle.id, ratings=[4], n_viz=1, duration_seconds=60
        )
        _make_participant(
            "control", hairstyle.id, ratings=[5], n_viz=1, duration_seconds=60
        )

        m = _experiment_metrics()
        hist = m["rating_hist"]["control"]
        assert hist == [1, 0, 1, 0, 1, 0, 1, 1]


def test_experiment_metrics_viz_histogram_caps_at_6_plus(app, hairstyle):
    """Participants with 6+ visualizations all land in the final '6+' bin."""
    with app.app_context():
        _make_participant(
            "experimental",
            hairstyle.id,
            ratings=[5] * 6,
            n_viz=6,
            n_ai_rec=0,
            duration_seconds=60,
        )
        _make_participant(
            "experimental",
            hairstyle.id,
            ratings=[5] * 10,
            n_viz=10,
            n_ai_rec=0,
            duration_seconds=60,
        )

        m = _experiment_metrics()
        assert m["viz_hist"]["experimental"][6] == 2
        assert m["viz_hist"]["experimental"][5] == 0


def test_experiment_metrics_ignores_non_study_groups(app, hairstyle):
    """Rows with an unexpected experiment_group value do not appear in the per-group breakdown."""
    with app.app_context():
        sid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        db.session.add(Consent(session_id=sid, experiment_group="unknown"))
        db.session.add(
            ExperimentSession(
                session_id=sid,
                experiment_group="unknown",
                started_at=now,
                last_ping_at=now,
                ended_at=now,
                duration_seconds=60,
            )
        )
        db.session.commit()

        m = _experiment_metrics()
        assert m["n_total"] == 0
        assert m["n_control"] == 0
        assert m["n_experimental"] == 0
