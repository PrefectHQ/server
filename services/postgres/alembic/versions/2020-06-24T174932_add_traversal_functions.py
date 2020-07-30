"""
Add traversal functions

Revision ID: 3398e4807bfb
Revises: c4d792bdd05e
Create Date: 2020-06-24 17:49:32.058745

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "3398e4807bfb"
down_revision = "c4d792bdd05e"
branch_labels = None
depends_on = None


def upgrade():

    op.execute("CREATE SCHEMA utility;")
    op.create_table(
        "traversal",
        sa.Column("tenant_id", UUID),
        sa.Column("task_id", UUID),
        sa.Column("depth", sa.Integer),
        schema="utility",
    )

    op.execute(
        """
        CREATE FUNCTION utility.downstream_tasks(start_task_ids UUID[], depth_limit integer default 50)
        RETURNS SETOF utility.traversal AS

        $$
        with recursive traverse(tenant_id, task_id, depth) AS (
            SELECT
                -- a tenant id
                task.tenant_id,

                -- a task id
                task.id,

                -- the depth
                0

            FROM task

            -- the starting point
            WHERE task.id = ANY(start_task_ids)

            UNION

            SELECT

                -- a tenant id
                edge.tenant_id,

                -- a new task
                edge.downstream_task_id,

                -- increment the depth
                traverse.depth + 1

            FROM traverse
            INNER JOIN edge
            ON
                edge.upstream_task_id = traverse.task_id
            WHERE

                -- limit traversal to the lesser of 50 tasks or the depth_limit
                traverse.depth < 50
                AND traverse.depth < depth_limit
            )
        SELECT
            tenant_id,
            task_id,
            MAX(traverse.depth) as depth
        FROM traverse

        -- group by task_id to remove duplicate observations
        GROUP BY task_id, tenant_id

        -- sort by the last time a task was visited
        ORDER BY MAX(traverse.depth), task_id, tenant_id

        $$ LANGUAGE sql STABLE;
    """
    )
    op.execute(
        """
        CREATE FUNCTION utility.upstream_tasks(start_task_ids UUID[], depth_limit integer default 50)
        RETURNS SETOF utility.traversal AS

        $$
        with recursive traverse(tenant_id, task_id, depth) AS (
            SELECT

                -- a tenant id
                task.tenant_id,

                -- a task id
                task.id,

                -- the depth
                0

            FROM task

            -- the starting point
            WHERE task.id = ANY(start_task_ids)

            UNION

            SELECT
                -- a tenant id
                edge.tenant_id,

                -- a new task
                edge.upstream_task_id,

                -- increment the depth
                traverse.depth + 1

            FROM traverse
            INNER JOIN edge
            ON
                edge.downstream_task_id = traverse.task_id
            WHERE

                -- limit traversal to the lesser of 50 tasks or the depth_limit
                traverse.depth < 50
                AND traverse.depth < depth_limit
            )
        SELECT
            tenant_id,
            task_id,
            MAX(traverse.depth) as depth
        FROM traverse

        -- group by task_id to remove duplicate observations
        GROUP BY task_id, tenant_id

        -- sort by the last time a task was visited
        ORDER BY MAX(traverse.depth), task_id, tenant_id

        $$ LANGUAGE sql STABLE;
    """
    )


def downgrade():
    op.execute("DROP SCHEMA utility CASCADE;")
