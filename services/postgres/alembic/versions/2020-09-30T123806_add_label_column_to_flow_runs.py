"""
Add label column to flow runs

Revision ID: 24f10aeee83e
Revises: 850b76d44332
Create Date: 2020-09-30 12:38:06.915340

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "24f10aeee83e"
down_revision = "850b76d44332"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run", sa.Column("labels", JSONB, nullable=False, server_default="[]")
    )


def downgrade():
    op.drop_column("flow_run", "labels")
