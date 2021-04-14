"""
Allow Flow.project_id to be nullable

Revision ID: d2b731ef9bb7
Revises: 459a61bedc9e
Create Date: 2021-04-14 12:17:00.505922

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "d2b731ef9bb7"
down_revision = "459a61bedc9e"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("flow", "project_id", nullable=True)


def downgrade():
    # Leave the column nullable in a downgrade
    pass
