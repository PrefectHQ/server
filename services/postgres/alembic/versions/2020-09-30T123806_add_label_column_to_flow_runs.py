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
    op.execute(
        """
    WITH runs_to_update AS (
	SELECT
		flow_run.id,
		COALESCE(
			flow_group.labels,
			flow.environment -> 'labels',
			'[]')::JSONB as new_labels
	from flow_run
	join flow on flow_run.flow_id = flow.id
	join flow_group on flow.flow_group_id = flow_group.id
	where flow_run.state = 'Scheduled'
	)
    update flow_run
    set labels = runs_to_update.new_labels
    from runs_to_update
    where flow_run.id = runs_to_update.id;
    """
    )


def downgrade():
    op.drop_column("flow_run", "labels")
