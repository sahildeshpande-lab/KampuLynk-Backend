"""initial schema

Revision ID: 47f07776e05b
Revises: 
Create Date: 2026-06-09 10:46:25.767962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '47f07776e05b_usertable_changes'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade():


    # Copy data if needed
    op.execute("""
        UPDATE users
        SET
            first_name = COALESCE(first_name, split_part(full_name, ' ', 1)),
            last_name = COALESCE(
                last_name,
                CASE
                    WHEN position(' ' in full_name) > 0
                    THEN substring(full_name from position(' ' in full_name) + 1)
                    ELSE ''
                END
            )
        WHERE full_name IS NOT NULL
    """)

    # Drop old columns
    op.drop_column("users", "full_name")
    op.drop_column("users", "is_active")


def downgrade():

    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=150), nullable=True)
    )

    op.execute("""
        UPDATE users
        SET full_name = concat_ws(' ', first_name, last_name)
    """)

    op.drop_column("users", "first_name")
    op.drop_column("users", "last_name")

    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=True)
    )