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
revision = "7ca57ea2fdff"
down_revision = "57ac2cb01ac1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run", sa.Column("run_config", JSONB, nullable=True, server_default=None)
    )
    op.add_column(
        "flow_group", sa.Column("run_config", JSONB, nullable=True, server_default=None)
    )
    # This query updates all currently scheduled flow runs to add the run_config field
    # from the corresponding flow.
    op.execute(
        """
        WITH runs_to_update AS (
            SELECT
                flow_run.id,
                flow.run_config
            from flow_run
            join flow on flow_run.flow_id = flow.id
            where flow_run.state = 'Scheduled' OR flow_run.updated > NOW() - interval '1 day'
        )
        update flow_run
        set run_config = runs_to_update.run_config
        from runs_to_update
        where flow_run.id = runs_to_update.id;
        """
    )


def downgrade():
    op.drop_column("flow_run", "run_config")
    op.drop_column("flow_group", "run_config")
