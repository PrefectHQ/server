"""
add flow concurrency limit

Revision ID: 8d9176f5e9f5
Revises: 70528cee0d2b
Create Date: 2020-09-09 13:34:55.226577

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "8d9176f5e9f5"
down_revision = "70528cee0d2b"
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
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("limit", sa.Integer, nullable=False),
    )
    op.execute(
        """
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON flow_concurrency_limit
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )

    op.execute(
        """
        ALTER TABLE ONLY flow_concurrency_limit ADD CONSTRAINT flow_concurrency_limit_uq_name_tenant_id UNIQUE (tenant_id, name);
        """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE flow_concurrency_limit CASCADE;
    """
    )
