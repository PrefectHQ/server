"""
Add artifact api

Revision ID: 3c87ad7e0b71
Revises: 24f10aeee83e
Create Date: 2020-10-21 14:11:27.409161

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "3c87ad7e0b71"
down_revision = "24f10aeee83e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_run_artifact",
        sa.Column(
            "id", UUID, primary_key=True, server_default=sa.func.gen_random_uuid()
        ),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "tenant_id",
            UUID,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "task_run_id",
            UUID,
            sa.ForeignKey("task_run.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
    )

    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON task_run_artifact
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )


def downgrade():
    op.drop_table("task_run_artifact")
