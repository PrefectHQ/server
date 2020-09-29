"""
Add flow run config

Revision ID: 850b76d44332
Revises: e148cf9f1e5b
Create Date: 2020-09-21 14:53:18.321017

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "850b76d44332"
down_revision = "e148cf9f1e5b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow", sa.Column("run_config", JSONB, nullable=True))


def downgrade():
    op.drop_column("flow", "run_config")
