"""
Add index for task run names

Revision ID: 57ac2cb01ac1
Revises: 3c87ad7e0b71
Create Date: 2020-12-02 13:09:56.377051

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "57ac2cb01ac1"
down_revision = "3c87ad7e0b71"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX
        ix_task_run_name_trgm
        ON task_run USING GIN (name gin_trgm_ops)
        WHERE name IS NOT NULL
        """
    )


def downgrade():
    op.drop_index("ix_task_run_name_trgm", table_name="task_run")
