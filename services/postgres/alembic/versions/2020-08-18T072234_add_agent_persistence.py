"""
Add agent persistence

Revision ID: 37e7552ab316
Revises: c1f317aa658c
Create Date: 2020-08-18 07:22:34.527630

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "37e7552ab316"
down_revision = "c1f317aa658c"
branch_labels = None
depends_on = None


def upgrade():
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
            UUID(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
    )

    op.execute(
        f"""
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON agent
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )

    op.create_table(
        "agent_instance",
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
            UUID(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "agent_id",
            UUID(),
            sa.ForeignKey("agent.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String),
        sa.Column("type", sa.String),
        sa.Column("core_version", sa.String),
        sa.Column("labels", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "last_query",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.execute(
        f"""
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON agent_instance
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )

    op.add_column(
        "flow_run",
        sa.Column(
            "agent_instance_id",
            UUID,
            sa.ForeignKey("agent_instance.id", ondelete="SET NULL"),
        ),
    )


def downgrade():
    op.drop_column("flow_run", "agent_instance_id")
    op.drop_table("agent_instance")
    op.drop_table("agent")
