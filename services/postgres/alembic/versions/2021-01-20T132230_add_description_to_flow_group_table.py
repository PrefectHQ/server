"""
Add description to flow group table

Revision ID: 9116e81c6dc2
Revises: 7ca57ea2fdff
Create Date: 2021-01-20 13:22:30.242349

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = '9116e81c6dc2'
down_revision = '7ca57ea2fdff'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_group", sa.Column("description", JSONB, nullable=True, server_default=None)
    )


def downgrade():
    op.drop_column("flow_group", "description")
