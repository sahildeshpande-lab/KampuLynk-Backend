"""add_email_verified_at_to_users

Revision ID: a1b2c3d4e5f6
Revises: 32293d02ec0b
Create Date: 2026-06-10 11:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '32293d02ec0b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'email_verified_at')
