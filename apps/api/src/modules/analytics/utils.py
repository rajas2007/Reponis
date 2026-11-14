from datetime import date, datetime, time, timezone


def get_week_start(dt: datetime | date) -> date:
    """
    Returns the Monday 00:00:00 UTC date of the week for the given timestamp/date.
    ISO weekday: Monday is 1, Sunday is 7.
    """
    if isinstance(dt, datetime):
        # Ensure UTC timezone if tz-aware, or treat as UTC if naive
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        d = dt.date()
    else:
        d = dt

    # ISO weekday: Monday is 1, Sunday is 7
    days_since_monday = d.isoweekday() - 1
    from datetime import timedelta

    monday_date = d - timedelta(days=days_since_monday)
    return monday_date


def get_week_start_datetime(dt: datetime | date) -> datetime:
    """
    Returns the Monday 00:00:00 UTC datetime for the given timestamp/date.
    """
    monday_date = get_week_start(dt)
    return datetime.combine(monday_date, time.min, tzinfo=timezone.utc)
