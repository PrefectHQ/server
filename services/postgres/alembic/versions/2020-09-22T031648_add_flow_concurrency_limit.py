"""
add flow concurrency limit

Revision ID: 0ebcc469a91d
Revises: 9cb7539b7363
Create Date: 2020-09-22 03:16:48.797370

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "0ebcc469a91d"
down_revision = "9cb7539b7363"
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
