# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

"""
Create extensions and initial settings

Revision ID: 27811b58307b
Revises: 
Create Date: 2020-06-24 09:04:36.600846

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "27811b58307b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        CREATE EXTENSION IF NOT EXISTS "pg_trgm";
        SET TIME ZONE 'UTC';
        """
    )


def downgrade():
    pass
