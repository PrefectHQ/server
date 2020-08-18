"""
Add agent persistence

Revision ID: 37e7552ab316
Revises: c1f317aa658c
Create Date: 2020-08-18 07:22:34.527630

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY


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
            "tenant_id",
            UUID(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String),
        sa.Column("type", sa.String),
        sa.Column("core_version", sa.String),
        sa.Column("labels", ARRAY(sa.String)),
        sa.Column(
            "last_query_time",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        # TODO: Auth in other repo
    )


def downgrade():
    op.drop_table("agent")
