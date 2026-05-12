from __future__ import annotations

from dataclasses import dataclass

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
            role="admin",
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
        )
    ]
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


def seed_demo_data() -> int:
    Base.metadata.create_all(bind=engine)

    created = 0
    skipped = 0

    db = SessionLocal()
    try:
        for row in _seed_plan():
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
    seed_demo_data()
