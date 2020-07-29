"""
Create message table

Revision ID: b9086bd4b962
Revises: 3398e4807bfb
Create Date: 2020-07-01 18:15:28.691752

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "b9086bd4b962"
down_revision = "3398e4807bfb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message",
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
        sa.Column("read", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("type", sa.String),
        sa.Column("text", sa.String),
        sa.Column("content", JSONB, nullable=False, server_default="{}"),
    )

    op.execute(
        f"""
        CREATE TRIGGER update_timestamp
        BEFORE UPDATE ON message
        FOR EACH ROW
        EXECUTE PROCEDURE set_updated_timestamp();
        """
    )


def downgrade():
    op.drop_table("message")
