"""drop user_academic_interests and migrate to users json column

Revision ID: 74bd36f52e39
Revises: c6ad758dd864
Create Date: 2026-06-09 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '74bd36f52e39'
down_revision: Union[str, Sequence[str], None] = 'c6ad758dd864'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure the JSON column exists on the users table (if it doesn't already)
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS academic_interests JSON DEFAULT '[]' NOT NULL;
        """
    )

    # 2. Migrate data from user_academic_interests to users.academic_interests
    op.execute(
        """
        UPDATE users u
        SET academic_interests = COALESCE(
            (
                SELECT json_agg(interest)
                FROM user_academic_interests uai
                WHERE uai.user_id = u.id
            ),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM user_academic_interests uai WHERE uai.user_id = u.id
        );
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS user_academic_interests;
        """
    )


def downgrade() -> None:
    # Re-create user_academic_interests table
    op.create_table(
        "user_academic_interests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interest", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
