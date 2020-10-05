"""
add flow concurrency limit

Revision ID: b9eedd397f54
Revises: 24f10aeee83e
Create Date: 2020-10-04 15:37:53.738144

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "b9eedd397f54"
down_revision = "24f10aeee83e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flow_concurrency_limit",
        sa.Column(
            "id", UUID, primary_key=True, server_default=sa.func.gen_random_uuid()
        ),
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
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
        sa.Column("name", sa.String(length=100), nullable=False, index=True),
        sa.Column("limit", sa.Integer, nullable=False),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON flow_concurrency_limit
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )


def downgrade():
    op.drop_table("flow_concurrency_limit")
