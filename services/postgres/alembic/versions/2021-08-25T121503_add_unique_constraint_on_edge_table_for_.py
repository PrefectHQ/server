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
    --the new constraint cannot be applied if there are any duplicate edges in the edge table
    --because edges are used only for UI Schematics, this has no effect on application logic or behavior
    WITH duplicate_edges AS (
	SELECT
            MIN(id::text)::UUID AS bad_id,
            upstream_task_id,
            downstream_task_id
	FROM
            edge
	GROUP BY
            upstream_task_id,
            downstream_task_id
	HAVING
            COUNT(*) > 1
    ) DELETE FROM edge
        WHERE id IN (SELECT bad_id FROM duplicate_edges);
        """
    )
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
