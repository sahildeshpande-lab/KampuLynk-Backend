from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import exists, or_ ,func
from sqlalchemy.orm import Session 

from ..db.db import get_db
from ..models.model import Post, User, UserAcademicInterest
from ..models.schemas import ApiResponse
from ..services import post_service
from .shared import _public_user, api_response, get_current_user_optional

DISCOVERY_TAG = "6] Search & Discovery"

router = APIRouter(tags=[DISCOVERY_TAG])


def _split_csv(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for raw in value.split(","):
            cleaned = raw.strip()
            if cleaned:
                items.append(cleaned)
    # stable de-dupe, preserve order
    return list(dict.fromkeys(items))

def _interest_exists_any(patterns: list[str]):
    if not patterns:
        return None
    return exists().where(
        (UserAcademicInterest.user_id == User.id)
        & or_(*(UserAcademicInterest.interest.ilike(pattern) for pattern in patterns))
    )


def _normalize_interest(value: str) -> str:
    return value.strip().lower()


@router.get("/discovery/users/search", response_model=ApiResponse)
def search_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    q: str | None = Query(default=None, max_length=200, description="Search by name/email/keyword/hashtag"),
    name: str | None = Query(default=None, max_length=150, description="Alias for q (name search)"),
    username: str | None = Query(default=None, max_length=150, description="Alias for q (email/username search)"),
    keyword: str | None = Query(default=None, max_length=200, description="Alias for q (keyword search)"),
    hashtag: Annotated[list[str] | None, Query()] = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """
    Search & Discovery (Users)

    Supports:
    - Search by `q` (name/email/keyword) and/or `hashtag` (matched against academic interests)
    """

    invalid_filter_keys = {
        "university",
        "major",
        "minor",
        "interest",
        "fieldOfStudy",
    }
    provided_filter_keys = [key for key in invalid_filter_keys if request.query_params.get(key)]
    if provided_filter_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Filter parameters are not supported on /discovery/users/search. "
                "Use /discovery/users/filter for: fieldOfStudy, interest, university, major, minor."
            ),
        )

    # Normalize query inputs
    query_text = (q or name or username or keyword or "").strip()
    hashtags = _split_csv(hashtag)
    hashtag_terms = [h.lstrip("#").strip() for h in hashtags if h and h.strip()]
    hashtag_terms = [t for t in hashtag_terms if t]

    base = db.query(User).filter(User.is_delete.is_(False))

    # Exclude self and blocked relationships when authenticated
    if current_user:
        base = base.filter(User.id != current_user.id)
        blocked_by_me = set(current_user.blocked_user_ids or [])
        if blocked_by_me:
            base = base.filter(~User.id.in_(blocked_by_me))

    # Discovery is public-facing by default; exclude private profiles
    base = base.filter(User.profile_visibility != "private")

    if hashtag_terms:
        hashtag_patterns = [f"%{term}%" for term in hashtag_terms]
        hashtag_exists = _interest_exists_any(hashtag_patterns)
        if hashtag_exists is not None:
            base = base.filter(hashtag_exists)

    if query_text:
        text = query_text
        if text.startswith("#"):
            # hashtag search -> interests
            normalized = text.lstrip("#").strip()
            if normalized:
                hashtag_exists = _interest_exists_any([f"%{normalized}%"])
                if hashtag_exists is not None:
                    base = base.filter(hashtag_exists)
        else:
            # Treat "@something" as a username/email handle search
            if text.startswith("@"):
                text = text[1:].strip()
            like = f"%{text}%"
            interest_exists = _interest_exists_any([like])
            interest_clause = interest_exists if interest_exists is not None else False
            username_clause = User.email.ilike(f"{text}@%")
            base = base.filter(
                or_(
                    func.concat(User.first_name, ' ', User.last_name).ilike(like),
                    User.email.ilike(like),
                    username_clause,
                    User.bio.ilike(like),
                    interest_clause,
                )
            )

    base = base.order_by(User.completeness_score.desc(), User.connections_count.desc())

    total = base.order_by(None).count()
    users = base.offset(offset).limit(limit).all()
    items = [_public_user(user) for user in users]

    message = "No data found" if total == 0 else "Users found"
    return api_response(
        message,
        {"items": items, "total": total, "limit": limit, "offset": offset},
    )


@router.get("/discovery/users/filter", response_model=ApiResponse)
def filter_users(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    university: str | None = Query(default=None, max_length=255),
    major: str | None = Query(default=None, max_length=150),
    minor: str | None = Query(default=None, max_length=150),
    interest: Annotated[list[str] | None, Query()] = None,
    fieldOfStudy: str | None = Query(default=None, max_length=150, description="Alias for major"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """
    Search & Discovery (Users Filters)

    Supports:
    - Filters by fieldOfStudy, interest(s), university, major, and minor
    """

    interests = _split_csv(interest)

    base = db.query(User).filter(User.is_delete.is_(False))

    if current_user:
        base = base.filter(User.id != current_user.id)
        blocked_by_me = set(current_user.blocked_user_ids or [])
        if blocked_by_me:
            base = base.filter(~User.id.in_(blocked_by_me))

    base = base.filter(User.profile_visibility != "private")

    if university:
        base = base.filter(User.university.ilike(f"%{university.strip()}%"))
    if major or fieldOfStudy:
        major_value = (major or fieldOfStudy or "").strip()
        if major_value:
            base = base.filter(User.major.ilike(f"%{major_value}%"))
    if minor:
        base = base.filter(User.minor.ilike(f"%{minor.strip()}%"))
    if interests:
        patterns = list(dict.fromkeys([*interests, *(f"%{i}%" for i in interests)]))
        interest_exists = _interest_exists_any(patterns)
        if interest_exists is not None:
            base = base.filter(interest_exists)

    base = base.order_by(User.completeness_score.desc(), User.connections_count.desc())
    total = base.order_by(None).count()
    users = base.offset(offset).limit(limit).all()
    items = [_public_user(user) for user in users]

    return api_response(
        "Users filtered",
        {"items": items, "total": total, "limit": limit, "offset": offset},
    )


@router.get("/discovery/users/recommendations", response_model=ApiResponse)
def recommend_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    connected_ids = set(current_user.connected_user_ids or [])
    blocked_ids = set(current_user.blocked_user_ids or [])
    excluded_ids = connected_ids | blocked_ids | {current_user.id}

    candidate_users = (
        db.query(User)
        .filter(
            User.is_delete.is_(False),
            User.profile_visibility != "private",
            ~User.id.in_(excluded_ids) if excluded_ids else True,
        )
        .all()
    )

    ranked_items: list[dict] = []
    for candidate in candidate_users:
        candidate_connections = set(candidate.connected_user_ids or [])
        mutual_count = len(connected_ids.intersection(candidate_connections))
        if current_user.id in (candidate.blocked_user_ids or []):
            continue
        ranked_items.append(
            {
                "user": candidate,
                "mutualConnections": mutual_count,
                "score": (
                    mutual_count,
                    int(candidate.connections_count or 0),
                    int(candidate.completeness_score or 0),
                ),
            }
        )

    ranked_items.sort(key=lambda row: row["score"], reverse=True)
    total = len(ranked_items)
    page_items = ranked_items[offset: offset + limit]
    data_items = []
    for row in page_items:
        user_payload = _public_user(row["user"])
        user_payload["mutualConnections"] = row["mutualConnections"]
        data_items.append(user_payload)

    return api_response(
        "Recommended users fetched",
        {"items": data_items, "total": total, "limit": limit, "offset": offset},
    )


@router.get("/discovery/posts/recommendations", response_model=ApiResponse)
def recommend_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    interests = {
        _normalize_interest(item.interest)
        for item in (current_user.academic_interests or [])
        if item.interest and item.interest.strip()
    }
    if not interests:
        return api_response(
            "Recommended posts fetched",
            {"items": [], "total": 0, "limit": limit, "offset": offset},
        )

    blocked_ids = set(current_user.blocked_user_ids or [])
    posts = (
        db.query(Post)
        .filter(
            Post.status == "published",
            Post.deleted_at.is_(None),
            Post.author_id != current_user.id,
            ~Post.author_id.in_(blocked_ids) if blocked_ids else True,
        )
        .order_by(Post.created_at.desc())
        .all()
    )

    ranked_posts: list[tuple[int, Post]] = []
    for post in posts:
        if not post.author or post.author.is_delete:
            continue
        author_interest_set = {
            _normalize_interest(item.interest)
            for item in (post.author.academic_interests or [])
            if item.interest and item.interest.strip()
        }
        overlap = len(interests.intersection(author_interest_set))
        if overlap <= 0:
            continue
        ranked_posts.append((overlap, post))

    ranked_posts.sort(key=lambda row: (row[0], row[1].created_at), reverse=True)
    total = len(ranked_posts)
    selected = ranked_posts[offset: offset + limit]
    items = [post_service.post_to_schema(db, post) for _, post in selected]

    return api_response(
        "Recommended posts fetched",
        {"items": items, "total": total, "limit": limit, "offset": offset},
    )
