"""
Add unique index for idempotency key

Revision ID: a666a3f4e422
Revises: 459a61bedc9e
Create Date: 2021-03-16 09:48:33.324078

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "a666a3f4e422"
down_revision = "459a61bedc9e"
branch_labels = None
depends_on = None


def upgrade():

    # before we can create a unique index, we to make sure there aren't
    # any duplicates. This query will find any flow id / idempotency key pairs
    # that have more than one match, and delete all but one of them.
    op.execute(
        """
        DELETE FROM flow_run fr
        USING (
            SELECT 
                flow_id,
                idempotency_key,
                MIN(ctid) as ctid
            FROM flow_run
            GROUP BY flow_id, idempotency_key
            HAVING COUNT(*) > 1
            ) fr2
        WHERE 
            fr.flow_id = fr2.flow_id
            AND fr.idempotency_key = fr2.idempotency_key
            AND fr.ctid <> fr2.ctid;
        """
    )

    op.execute(
        """
        DROP INDEX ix_flow_run_idempotency_key;
        CREATE UNIQUE INDEX ix_flow_run_idempotency_key_unique on flow_run (idempotency_key, flow_id);
        ALTER TABLE flow_run ADD CONSTRAINT ix_flow_run_idempotency_key_unique UNIQUE USING INDEX ix_flow_run_idempotency_key_unique;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE flow_run DROP CONSTRAINT ix_flow_run_idempotency_key_unique;
    
        CREATE INDEX ix_flow_run_idempotency_key
        on flow_run (idempotency_key);
        """
    )
