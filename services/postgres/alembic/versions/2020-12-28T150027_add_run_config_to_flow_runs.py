"""
Add run_config to flow runs and flow groups

Revision ID: 7ca57ea2fdff
Revises: 57ac2cb01ac1
Create Date: 2020-12-28 15:00:27.573816

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '7ca57ea2fdff'
down_revision = '57ac2cb01ac1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run", sa.Column("run_config", JSONB, nullable=True, server_default=None)
    )
    op.add_column(
        "flow_group", sa.Column("run_config", JSONB, nullable=True, server_default=None)
    )


def downgrade():
    op.drop_column("flow_run", "run_config")
    op.drop_column("flow_group", "run_config")
