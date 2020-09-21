"""
Add flow run config

Revision ID: 850b76d44332
Revises: 9cb7539b7363
Create Date: 2020-09-21 14:53:18.321017

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "850b76d44332"
down_revision = "9cb7539b7363"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow", sa.Column("run_config", JSONB, nullable=False, server_default="{}")
    )


def downgrade():
    op.drop_column("flow", "run_config")
