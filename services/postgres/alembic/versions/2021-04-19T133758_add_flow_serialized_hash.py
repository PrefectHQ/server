"""
Add 'Flow.serialized_hash'

Revision ID: e0e276cd1ec9
Revises: a666a3f4e422
Create Date: 2021-04-19 13:37:58.897204

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "e0e276cd1ec9"
down_revision = "a666a3f4e422"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow",
        sa.Column("serialized_hash", sa.String, nullable=True, index=True),
    )


def downgrade():
    op.drop_column("flow", "serialized_hash")
