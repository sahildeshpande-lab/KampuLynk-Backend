from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import os
from typing import Callable

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.model import DailyAnalytics, Post, User, UserActivity

DEFAULT_DAYS = int(os.getenv("DEFAULT_DAYS", "7"))
MAX_DAYS = int(os.getenv("MAX_DAYS", "90"))
DEFAULT_TOP_LIMIT = int(os.getenv("DEFAULT_TOP_LIMIT", "5"))
MAX_TOP_LIMIT = int(os.getenv("MAX_TOP_LIMIT", "20"))


def _utc_day_start(value: date) -> datetime:
    return datetime.combine(value, time.min).replace(tzinfo=timezone.utc)


def _safe_growth(today_value: int, yesterday_value: int) -> float:
    if yesterday_value == 0:
        return 100.0 if today_value > 0 else 0.0
    return round(((today_value - yesterday_value) / yesterday_value) * 100, 2)


def resolve_date_range(
    days: int = DEFAULT_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")
    if days < 1 or days > MAX_DAYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"days must be between 1 and {MAX_DAYS}")

    if start_date and end_date:
        return start_date, end_date
    if start_date and not end_date:
        return start_date, start_date + timedelta(days=days - 1)
    if end_date and not start_date:
        return end_date - timedelta(days=days - 1), end_date

    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=days - 1), today


def _build_daily_series(
    start_day: date,
    end_day: date,
    value_lookup: dict[date, int],
    value_key: str,
) -> list[dict]:
    items: list[dict] = []
    current = start_day
    while current <= end_day:
        items.append({"date": current.isoformat(), value_key: value_lookup.get(current, 0)})
        current += timedelta(days=1)
    return items


def _activity_users_by_day(db: Session, start_day: date, end_day: date) -> dict[date, set[str]]:
    start_at = _utc_day_start(start_day)
    end_at = _utc_day_start(end_day + timedelta(days=1))
    rows = (
        db.query(UserActivity.user_id, UserActivity.created_at)
        .filter(UserActivity.created_at >= start_at, UserActivity.created_at < end_at)
        .all()
    )
    output: dict[date, set[str]] = defaultdict(set)
    for user_id, created_at in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        output[created_at.astimezone(timezone.utc).date()].add(user_id)
    return output


def _new_users_by_day(db: Session, start_day: date, end_day: date) -> dict[date, int]:
    start_at = _utc_day_start(start_day)
    end_at = _utc_day_start(end_day + timedelta(days=1))
    rows = (
        db.query(User.created_at)
        .filter(User.created_at >= start_at, User.created_at < end_at)
        .all()
    )
    counter: dict[date, int] = defaultdict(int)
    for (created_at,) in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        counter[created_at.astimezone(timezone.utc).date()] += 1
    return counter


def dau_trend(
    db: Session,
    days: int = DEFAULT_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start_day, end_day = resolve_date_range(days=days, start_date=start_date, end_date=end_date)
    active_users_lookup = _activity_users_by_day(db, start_day, end_day)
    dau_lookup = {day: len(users) for day, users in active_users_lookup.items()}
    trend = _build_daily_series(start_day, end_day, dau_lookup, "dau")
    today_dau = trend[-1]["dau"] if trend else 0
    yesterday_dau = trend[-2]["dau"] if len(trend) > 1 else 0
    return {
        "today_dau": today_dau,
        "yesterday_dau": yesterday_dau,
        "growth_percentage": _safe_growth(today_dau, yesterday_dau),
        "trend": trend,
        "range": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
    }


def new_user_trend(
    db: Session,
    days: int = DEFAULT_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start_day, end_day = resolve_date_range(days=days, start_date=start_date, end_date=end_date)
    new_user_lookup = _new_users_by_day(db, start_day, end_day)
    trend = _build_daily_series(start_day, end_day, new_user_lookup, "new_users")
    today_new_users = trend[-1]["new_users"] if trend else 0
    yesterday_new_users = trend[-2]["new_users"] if len(trend) > 1 else 0
    return {
        "today_new_users": today_new_users,
        "yesterday_new_users": yesterday_new_users,
        "growth_percentage": _safe_growth(today_new_users, yesterday_new_users),
        "trend": trend,
        "range": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
    }


def total_users(db: Session) -> int:
    return int(db.query(func.count(User.id)).scalar() or 0)


def top_universities(db: Session, limit: int = DEFAULT_TOP_LIMIT) -> list[dict]:
    limited = min(max(limit, 1), MAX_TOP_LIMIT)
    rows = (
        db.query(User.university, func.count(User.id))
        .filter(User.university.isnot(None), func.trim(User.university) != "")
        .group_by(User.university)
        .order_by(func.count(User.id).desc(), User.university.asc())
        .limit(limited)
        .all()
    )
    return [{"university": university, "count": int(count)} for university, count in rows]


def top_majors(db: Session, limit: int = DEFAULT_TOP_LIMIT) -> list[dict]:
    limited = min(max(limit, 1), MAX_TOP_LIMIT)
    rows = (
        db.query(User.major, func.count(User.id))
        .filter(User.major.isnot(None), func.trim(User.major) != "")
        .group_by(User.major)
        .order_by(func.count(User.id).desc(), User.major.asc())
        .limit(limited)
        .all()
    )
    return [{"major": major, "count": int(count)} for major, count in rows]


def _country_from_location(location: str | None) -> str | None:
    if not location:
        return None
    normalized = location.strip()
    if not normalized:
        return None
    if "," not in normalized:
        return normalized
    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if not parts:
        return None
    return parts[-1]


def country_distribution(db: Session, limit: int = DEFAULT_TOP_LIMIT) -> list[dict]:
    limited = min(max(limit, 1), MAX_TOP_LIMIT)
    explicit_country_rows = (
        db.query(User.country, func.count(User.id))
        .filter(User.country.isnot(None), func.trim(User.country) != "")
        .group_by(User.country)
        .order_by(func.count(User.id).desc(), User.country.asc())
        .limit(limited)
        .all()
    )
    if explicit_country_rows:
        return [{"country": country, "count": int(count)} for country, count in explicit_country_rows]

    rows = db.query(User.location).filter(User.location.isnot(None), func.trim(User.location) != "").all()
    bucket: dict[str, int] = defaultdict(int)
    for (location,) in rows:
        country = _country_from_location(location)
        if not country:
            continue
        bucket[country] += 1
    sorted_items = sorted(bucket.items(), key=lambda item: (-item[1], item[0]))
    return [{"country": country, "count": count} for country, count in sorted_items[:limited]]


def _daily_aggregates_lookup(db: Session, start_day: date, end_day: date) -> dict[date, DailyAnalytics]:
    rows = db.query(DailyAnalytics).filter(DailyAnalytics.date >= start_day, DailyAnalytics.date <= end_day).all()
    return {row.date: row for row in rows}


def _materialize_daily_aggregate(
    db: Session,
    day: date,
    daily_dau: int,
    daily_new_users: int,
    cumulative_users_counter: Callable[[date], int],
    daily_total_posts_counter: Callable[[date], int],
) -> DailyAnalytics:
    entity = (
        db.query(DailyAnalytics)
        .filter(DailyAnalytics.date == day)
        .first()
    )
    if not entity:
        entity = DailyAnalytics(date=day)
        db.add(entity)
    entity.dau = daily_dau
    entity.new_users = daily_new_users
    entity.total_users = cumulative_users_counter(day)
    entity.total_posts = daily_total_posts_counter(day)
    db.flush()
    return entity


def aggregate_daily_analytics(
    db: Session,
    start_day: date,
    end_day: date,
) -> None:
    activity_users_lookup = _activity_users_by_day(db, start_day, end_day)
    new_user_lookup = _new_users_by_day(db, start_day, end_day)

    def cumulative_users_counter(day: date) -> int:
        return int(
            db.query(func.count(User.id))
            .filter(User.created_at < _utc_day_start(day + timedelta(days=1)))
            .scalar()
            or 0
        )

    def daily_total_posts_counter(day: date) -> int:
        start_at = _utc_day_start(day)
        end_at = _utc_day_start(day + timedelta(days=1))
        return int(
            db.query(func.count(Post.id))
            .filter(Post.created_at >= start_at, Post.created_at < end_at)
            .scalar()
            or 0
        )

    current = start_day
    while current <= end_day:
        _materialize_daily_aggregate(
            db=db,
            day=current,
            daily_dau=len(activity_users_lookup.get(current, set())),
            daily_new_users=int(new_user_lookup.get(current, 0)),
            cumulative_users_counter=cumulative_users_counter,
            daily_total_posts_counter=daily_total_posts_counter,
        )
        current += timedelta(days=1)
    db.commit()


def dashboard(
    db: Session,
    days: int = DEFAULT_DAYS,
    start_date: date | None = None,
    end_date: date | None = None,
    top_limit: int = DEFAULT_TOP_LIMIT,
) -> dict:
    start_day, end_day = resolve_date_range(days=days, start_date=start_date, end_date=end_date)

    # No scheduler exists in this project, so we materialize aggregates during reads
    # for predictable dashboard performance on repeated calls.
    aggregate_daily_analytics(db, start_day, end_day)
    aggregate_lookup = _daily_aggregates_lookup(db, start_day, end_day)

    dau_lookup = {day: row.dau for day, row in aggregate_lookup.items()}
    new_user_lookup = {day: row.new_users for day, row in aggregate_lookup.items()}
    dau_items = _build_daily_series(start_day, end_day, dau_lookup, "dau")
    new_user_items = _build_daily_series(start_day, end_day, new_user_lookup, "new_users")

    today_dau = dau_items[-1]["dau"] if dau_items else 0
    yesterday_dau = dau_items[-2]["dau"] if len(dau_items) > 1 else 0
    today_new_users = new_user_items[-1]["new_users"] if new_user_items else 0
    yesterday_new_users = new_user_items[-2]["new_users"] if len(new_user_items) > 1 else 0

    return {
        "summary": {
            "total_users": total_users(db),
            "today_dau": today_dau,
            "yesterday_dau": yesterday_dau,
            "dau_growth_percentage": _safe_growth(today_dau, yesterday_dau),
            "today_new_users": today_new_users,
            "new_user_growth_percentage": _safe_growth(today_new_users, yesterday_new_users),
        },
        "dau_trend": dau_items,
        "new_user_trend": new_user_items,
        "top_universities": top_universities(db, limit=top_limit),
        "country_distribution": country_distribution(db, limit=top_limit),
        "top_majors": top_majors(db, limit=top_limit),
        "range": {"start_date": start_day.isoformat(), "end_date": end_day.isoformat()},
    }
