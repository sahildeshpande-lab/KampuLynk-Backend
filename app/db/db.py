import os

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import load_env_files

load_env_files()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/ksolves")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def migrate_legacy_users_table():
    if not DATABASE_URL.startswith("postgresql"):
        return

    with engine.begin() as connection:
        users_exists = connection.execute(
            text("select to_regclass('public.users') is not null")
        ).scalar()
        if not users_exists:
            return

        id_type = connection.execute(
            text(
                """
                select data_type
                from information_schema.columns
                where table_schema = 'public'
                  and table_name = 'users'
                  and column_name = 'id'
                """
            )
        ).scalar()

        if id_type == "integer":
            connection.execute(text("alter table users alter column id drop default"))
            connection.execute(text("alter table users alter column id type varchar(36) using id::varchar"))

        name_exists = connection.execute(
            text(
                """
                select exists (
                    select 1
                    from information_schema.columns
                    where table_schema = 'public'
                      and table_name = 'users'
                      and column_name = 'name'
                )
                """
            )
        ).scalar()

        connection.execute(text("alter table users add column if not exists full_name varchar(150)"))
        if name_exists:
            connection.execute(text("update users set full_name = coalesce(full_name, name, email)"))
        else:
            connection.execute(text("update users set full_name = coalesce(full_name, email)"))
        connection.execute(text("alter table users alter column full_name set not null"))

        statements = [
            "alter table users add column if not exists password_hash varchar(255)",
            "alter table users add column if not exists role varchar(30) not null default 'user'",
            "alter table users add column if not exists login_type varchar(30) not null default 'email'",
            "alter table users add column if not exists profile_photo_url varchar(1000)",
            "alter table users add column if not exists banner_photo_url varchar(1000)",
            "alter table users add column if not exists university varchar(255)",
            "alter table users add column if not exists major varchar(150)",
            "alter table users add column if not exists minor varchar(150)",
            "alter table users add column if not exists education_level varchar(50)",
            "alter table users add column if not exists bio varchar(500)",
            "alter table users add column if not exists academic_interests json not null default '[]'::json",
            "alter table users add column if not exists graduation_date varchar(7)",
            "alter table users add column if not exists location varchar(255)",
            "alter table users add column if not exists country varchar(120)",
            "alter table users add column if not exists profile_visibility varchar(30) not null default 'public'",
            "alter table users add column if not exists completeness_score integer not null default 0",
            """alter table users add column if not exists notification_preferences json not null default '{"email": true, "push": true, "inApp": true}'::json""",
            "alter table users add column if not exists is_email_verified boolean not null default false",
            "alter table users add column if not exists is_active boolean not null default true",
            "alter table users add column if not exists consent_given boolean not null default false",
            "alter table users add column if not exists invitation_code varchar(100)",
            "alter table users add column if not exists online_presence boolean not null default false",
            "alter table users add column if not exists welcome_message varchar(255)",
            "alter table users add column if not exists connections_count integer not null default 0",
            "alter table users add column if not exists posts_count integer not null default 0",
            "alter table users add column if not exists blocked_user_ids json not null default '[]'::json",
            "alter table users add column if not exists reported_user_ids json not null default '[]'::json",
            "alter table users add column if not exists following_user_ids json not null default '[]'::json",
            "alter table users add column if not exists connection_request_user_ids json not null default '[]'::json",
            "alter table users add column if not exists connected_user_ids json not null default '[]'::json",
            "alter table users add column if not exists created_at timestamp with time zone not null default now()",
            "alter table users add column if not exists updated_at timestamp with time zone not null default now()",
            "create index if not exists ix_users_id on users (id)",
            "create unique index if not exists ix_users_email on users (email)",
            "create index if not exists ix_users_role on users (role)",
            "create index if not exists ix_users_university on users (university)",
            "create index if not exists ix_users_major on users (major)",
            "create index if not exists ix_users_minor on users (minor)",
            "create index if not exists ix_users_education_level on users (education_level)",
            "create index if not exists ix_users_country on users (country)",
        ]
        for statement in statements:
            connection.execute(text(statement))

        notification_statements = [
            "alter table user_notifications add column if not exists notification_type varchar(80) not null default 'send'",
            "alter table user_notifications add column if not exists target_type varchar(30) not null default 'direct'",
            "alter table user_notifications add column if not exists topic varchar(150)",
            "create index if not exists ix_user_notifications_notification_type on user_notifications (notification_type)",
            "create index if not exists ix_user_notifications_target_type on user_notifications (target_type)",
            "create index if not exists ix_user_notifications_topic on user_notifications (topic)",
        ]
        notifications_exists = connection.execute(
            text("select to_regclass('public.user_notifications') is not null")
        ).scalar()
        if notifications_exists:
            for statement in notification_statements:
                connection.execute(text(statement))

        posts_exists = connection.execute(
            text("select to_regclass('public.posts') is not null")
        ).scalar()
        if posts_exists:
            connection.execute(
                text("alter table posts add column if not exists engagement_enabled boolean not null default true")
            )
            """,
            "create unique index if not exists uq_daily_analytics_date on daily_analytics (date)",
            "create index if not exists ix_daily_analytics_date on daily_analytics (date)",
        ]
        for statement in daily_analytics_statements:
            connection.execute(text(statement))

        user_device_statements = [
            """
            create table if not exists user_devices (
                id varchar(36) primary key,
                user_id varchar(36) not null references users(id) on delete cascade,
                device_token varchar(4096) not null,
                platform varchar(30) not null,
                device_name varchar(150),
                is_active boolean not null default true,
                created_at timestamp with time zone not null default now(),
                updated_at timestamp with time zone not null default now(),
                last_used_at timestamp with time zone not null default now()
            )
            """,
            "create unique index if not exists uq_user_devices_device_token on user_devices (device_token)",
            "create index if not exists ix_user_devices_user_id on user_devices (user_id)",
            "create index if not exists ix_user_devices_device_token on user_devices (device_token)",
            "create index if not exists ix_user_devices_is_active on user_devices (is_active)",
        ]
        for statement in user_device_statements:
            connection.execute(text(statement))

        spam_keywords_statements = [
            """
            create table if not exists spam_keywords (
                id varchar(36) primary key,
                keyword varchar(255) unique not null,
                keyword_type varchar(30) not null,
                is_active boolean not null default true,
                created_by_user_id varchar(36) references users(id) on delete set null,
                updated_by_user_id varchar(36) references users(id) on delete set null,
                created_at timestamp with time zone not null default now(),
                updated_at timestamp with time zone not null default now()
            )
            """,
            "create index if not exists ix_spam_keywords_keyword on spam_keywords (keyword)",
            "create index if not exists ix_spam_keywords_keyword_type on spam_keywords (keyword_type)",
            "create index if not exists ix_spam_keywords_is_active on spam_keywords (is_active)",
        ]
        for statement in spam_keywords_statements:
            connection.execute(text(statement))


def ensure_platform_defaults():
    from ..models.model import PlatformConfig, SpamKeyword

    db = SessionLocal()
    try:
        if not db.query(PlatformConfig).filter(PlatformConfig.key == "comment.maxDepth").first():
            db.add(
                PlatformConfig(
                    key="comment.maxDepth",
                    value={"value": 3},
                    description="Maximum allowed nested comment depth.",
                )
            )
        if not db.query(PlatformConfig).filter(PlatformConfig.key == "moderation.blocklist").first():
            db.add(
                PlatformConfig(
                    key="moderation.blocklist",
                    value={"terms": ["damn", "shit", "buy followers", "free crypto", "click this scam", "visit shady link"]},
                    description="Case-insensitive blocked terms used during post/comment content scanning.",
                )
            )
        if db.query(SpamKeyword).count() == 0:
            defaults = [
                ("buy followers", "spam"),
                ("free crypto", "spam"),
                ("click this scam", "spam"),
                ("visit shady link", "spam"),
                ("damn", "profanity"),
                ("free", "profanity"),
                ("money", "profanity"),
                ("spam", "profanity"),
            ]
            for keyword, keyword_type in defaults:
                db.add(SpamKeyword(keyword=keyword, keyword_type=keyword_type, is_active=True))
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
