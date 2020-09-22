"""
Add index on agent_id

Revision ID: 9cb7539b7363
Revises: 70528cee0d2b
Create Date: 2020-09-16 17:13:14.928486

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "9cb7539b7363"
down_revision = "70528cee0d2b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_flow_run_agent_id",
        "flow_run",
        ["agent_id"],
    )


def downgrade():
    op.drop_index("ix_flow_run_agent_id", table_name="flow_run")
