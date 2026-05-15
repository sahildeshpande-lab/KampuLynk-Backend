from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import sys
import uuid

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.db import Base, SessionLocal, engine
from app.models.model import User, UserAcademicInterest, UserNotificationPreference
from app.routes.shared import _calculate_completeness, _hash_password


@dataclass(frozen=True)
class SeedUser:
    full_name: str
    email: str
    role: str
    university: str | None = None
    major: str | None = None
    minor: str | None = None
    education_level: str | None = None
    location: str | None = None
    bio: str | None = None
    profile_visibility: str = "public"
    interests: list[str] | None = None
    is_email_verified: bool = True
    is_active: bool = True
    consent_given: bool = True


DEFAULT_PASSWORD = "StrongPass123"


def _seed_plan() -> list[SeedUser]:
    users: list[SeedUser] = [
        SeedUser(
            full_name="=test_admin_Private",
            email="admin_private@demo.com",
            role="superadmin",
            university="Stanford",
            major="Biology",
            education_level="masters",
            location="USA",
            bio="Private profile for testing search/filter behavior.",
            profile_visibility="private",
            interests=["Genetics"],
        ),
         SeedUser(
            full_name="test_Private",
            email="user_private@demo.com",
            role="user",
            university="Stanford",
            major="Biology",
            education_level="masters",
            location="USA",
            bio="Private profile for testing search/filter behavior.",
            profile_visibility="private",
            interests=["Genetics"],
        ),
        SeedUser(
            full_name="test_Public",
            email="user_public@demo.com",
            role="user",
            university="MIT",
            major="CS",
            education_level="bachelors",
            location="USA",
            bio="Public profile for testing search/filter behavior.",
            profile_visibility="public",
            interests=["AI"],
        ),
        SeedUser(
            full_name="test_ConnectionsOnly",
            email="user_connections_only@demo.com",
            role="user",
            university="CMU",
            major="Mathematics",
            education_level="masters",
            location="USA",
            bio="Connections-only profile for testing visibility rules.",
            profile_visibility="connections_only",
            interests=["Data Science"],
        )
    ]
    return users


def _random_users_plan(
    total: int,
    *,
    seed: int | None = None,
    email_domain: str = "demo.com",
) -> list[SeedUser]:
    rng = random.Random(seed)

    roles = ["superadmin", "user", "viewer", "moderator"]
    universities = ["MIT", "Stanford", "Harvard", "CMU", "UCLA", "UC Berkeley", "Oxford", "Cambridge"]
    majors = ["CS", "Biology", "Economics", "Mathematics", "Physics", "Design", "Psychology", "Business"]
    education_levels = ["bachelors", "masters", "phd", "professional"]
    locations = ["USA", "India", "UK", "Canada", "Germany", "Singapore"]
    interests = ["AI", "Genetics", "Robotics", "Startups", "Data Science", "Neuroscience", "Product", "Finance"]

    planned_roles: list[str] = []
    if total <= 0:
        return []
    if total >= len(roles):
        planned_roles.extend(roles)
        planned_roles.extend(rng.choices(roles, k=total - len(roles)))
    else:
        planned_roles.extend(rng.sample(roles, k=total))
    rng.shuffle(planned_roles)

    users: list[SeedUser] = []
    visibilities = ["public", "private", "connections_only"]

    for index, role in enumerate(planned_roles, start=1):
        token = uuid.uuid4().hex[:10]
        full_name = f"Seed {role.title()} {index}"
        email = f"seed_{role}_{token}@{email_domain}"
        users.append(
            SeedUser(
                full_name=full_name,
                email=email,
                role=role,
                university=rng.choice(universities),
                major=rng.choice(majors),
                education_level=rng.choice(education_levels),
                location=rng.choice(locations),
                bio=f"Seeded {role} account for testing.",
                profile_visibility=rng.choice(visibilities),
                interests=rng.sample(interests, k=rng.randint(1, 3)),
                is_email_verified=True,
                is_active=True,
                consent_given=True,
            )
        )
    return users



def _create_user(row: SeedUser) -> User:
    user = User(
        full_name=row.full_name,
        email=row.email.lower(),
        password_hash=_hash_password(DEFAULT_PASSWORD),
        role=row.role,
        login_type="email",
        university=row.university,
        major=row.major,
        minor=row.minor,
        education_level=row.education_level,
        bio=row.bio,
        location=row.location,
        profile_visibility=row.profile_visibility,
        is_email_verified=row.is_email_verified,
        is_active=row.is_active,
        consent_given=row.consent_given,
    )
    user.academic_interests = [
        UserAcademicInterest(interest=interest) for interest in (row.interests or [])
    ]
    user.notification_preferences = UserNotificationPreference(email=True, push=True, in_app=True)
    user.completeness_score = _calculate_completeness(user)
    return user


def seed_demo_data(rows: list[SeedUser] | None = None) -> int:
    Base.metadata.create_all(bind=engine)

    created = 0
    skipped = 0

    db = SessionLocal()
    try:
        for row in (rows or _seed_plan()):
            exists_row = db.query(User.id).filter(User.email == row.email.lower()).first()
            if exists_row:
                skipped += 1
                continue
            user = _create_user(row)
            db.add(user)
            created += 1
        db.commit()
    finally:
        db.close()

    print(f"Seed complete. created={created} skipped={skipped}")
    print(f"Password for all seeded accounts: {DEFAULT_PASSWORD}")
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo users into the configured database.")
    parser.add_argument("--random", type=int, default=0, help="Create N random users across 4 roles.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (for repeatability).")
    parser.add_argument("--domain", type=str, default="demo.com", help="Email domain for random users.")
    args = parser.parse_args()

    if args.random and args.random > 0:
        seed_demo_data(_random_users_plan(args.random, seed=args.seed, email_domain=args.domain))
    else:
        seed_demo_data()
