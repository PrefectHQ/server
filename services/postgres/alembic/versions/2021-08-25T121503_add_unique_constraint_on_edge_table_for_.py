"""
Add unique constraint on edge table for task IDs

Revision ID: ac5747fb571c
Revises: a666a3f4e422
Create Date: 2021-08-25 12:15:03.581736

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ac5747fb571c"
down_revision = "a666a3f4e422"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE ONLY public.edge
        ADD CONSTRAINT edge_flow_id_task_ids_key UNIQUE (flow_id, downstream_task_id, upstream_task_id);
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE edge DROP CONSTRAINT edge_flow_id_task_ids_key;
        """
    )
