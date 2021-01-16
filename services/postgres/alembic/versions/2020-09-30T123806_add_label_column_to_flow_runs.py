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
    # this query looks at all currently scheduled flow runs, or more generally any flow
    # run that has been updated in the last day, and applies our standard label logic to it.
    # This ensures that active flow runs don't incorrectly receive `[]` as their label set,
    # which would cause delayed work and user frustration.
    # Note that flow runs not touched by this query will have `[]` as their labels regardless of
    # their flow label properties.
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
	where flow_run.state = 'Scheduled' OR flow_run.updated > NOW() - interval '1 day'
	)
    update flow_run
    set labels = runs_to_update.new_labels
    from runs_to_update
    where flow_run.id = runs_to_update.id;
    """
    )


def downgrade():
    op.drop_column("flow_run", "labels")
