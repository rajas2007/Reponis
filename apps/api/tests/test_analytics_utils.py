from datetime import date, datetime, timezone

from src.modules.analytics.utils import get_week_start, get_week_start_datetime


def test_get_week_start_boundaries():
    # Monday morning 00:00:00 UTC -> same day
    monday = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
    assert get_week_start(monday) == date(2026, 8, 10)
    assert get_week_start_datetime(monday) == monday

    # Monday afternoon
    monday_noon = datetime(2026, 8, 10, 15, 30, 0, tzinfo=timezone.utc)
    assert get_week_start(monday_noon) == date(2026, 8, 10)
    assert get_week_start_datetime(monday_noon) == monday

    # Wednesday
    wednesday = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert get_week_start(wednesday) == date(2026, 8, 10)

    # Sunday 23:59:59 UTC -> belongs to the Monday 6 days prior
    sunday_night = datetime(2026, 8, 16, 23, 59, 59, tzinfo=timezone.utc)
    assert get_week_start(sunday_night) == date(2026, 8, 10)
    assert get_week_start_datetime(sunday_night) == monday

    # Next Monday 00:00:00 UTC -> transitions to next week
    next_monday = datetime(2026, 8, 17, 0, 0, 0, tzinfo=timezone.utc)
    assert get_week_start(next_monday) == date(2026, 8, 17)
    assert get_week_start_datetime(next_monday) == next_monday

    # Test date object directly
    assert get_week_start(date(2026, 8, 10)) == date(2026, 8, 10)
    assert get_week_start(date(2026, 8, 16)) == date(2026, 8, 10)
    assert get_week_start(date(2026, 8, 17)) == date(2026, 8, 17)
