"""
Add flow run idempotency key

Revision ID: c4d792bdd05e
Revises: 72e2cd3e0469
Create Date: 2020-06-24 10:31:13.575325

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "c4d792bdd05e"
down_revision = "72e2cd3e0469"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow_run", sa.Column("idempotency_key", sa.String(), index=True))


def downgrade():
    op.drop_column("flow_run", "idempotency_key")
