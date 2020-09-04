"""
Add agent persistence

Revision ID: 4d189bc25279
Revises: 6611fd0ccc73
Create Date: 2020-09-03 16:34:24.932488

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "4d189bc25279"
down_revision = "6611fd0ccc73"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_config",
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
        sa.Column("name", sa.String),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
    )

    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON agent_config
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )

    op.create_table(
        "agent",
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
            "agent_config_id",
            UUID(),
            sa.ForeignKey("agent_config.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String),
        sa.Column("type", sa.String),
        sa.Column("core_version", sa.String),
        sa.Column("labels", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "last_queried",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON agent
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )

    op.add_column(
        "flow_run",
        sa.Column(
            "agent_id",
            UUID,
            sa.ForeignKey("agent.id", ondelete="SET NULL"),
        ),
    )


def downgrade():
    op.drop_column("flow_run", "agent_id")
    op.drop_table("agent")
    op.drop_table("agent_config")
