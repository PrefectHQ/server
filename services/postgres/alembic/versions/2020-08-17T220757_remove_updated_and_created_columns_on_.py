"""
Remove updated and created columns on log table

Revision ID: 5ac0d20cce89
Revises: c1f317aa658c
Create Date: 2020-08-17 22:07:57.445069

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "5ac0d20cce89"
down_revision = "c1f317aa658c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TRIGGER update_timestamp ON log;")
    op.drop_column("log", "created")
    op.drop_column("log", "updated")


def downgrade():
    op.add_column(
        "log",
        sa.Column(
            "created",
            sa.TIMESTAMP(timezone=True),
            index=True,
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "log",
        sa.Column(
            "updated",
            sa.TIMESTAMP(timezone=True),
            index=True,
            nullable=True,
            server_default=sa.func.now(),
        ),
    )

    op.execute(
        f"""
            CREATE TRIGGER update_timestamp
            BEFORE UPDATE ON log
            FOR EACH ROW
            EXECUTE PROCEDURE set_updated_timestamp();
            """
    )
