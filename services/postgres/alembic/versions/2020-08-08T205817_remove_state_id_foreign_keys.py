"""
Remove state_id foreign keys

Revision ID: c1f317aa658c
Revises: b9086bd4b962
Create Date: 2020-08-08 20:58:17.784897

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "c1f317aa658c"
down_revision = "b9086bd4b962"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP FUNCTION update_flow_run_with_latest_state CASCADE;
        DROP FUNCTION update_task_run_with_latest_state CASCADE;
        """
    )
    op.execute(
        """
        CREATE FUNCTION update_flow_run_with_latest_state() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
                    BEGIN
                        UPDATE flow_run
                        SET
                            version = new_latest_state.version,
                            -- below are fields that we only include for backwards-compatibility
                            state=new_latest_state.state,
                            serialized_state=new_latest_state.serialized_state,
                            state_start_time=new_latest_state.start_time,
                            state_timestamp=new_latest_state.timestamp,
                            state_message=new_latest_state.message,
                            state_result=new_latest_state.result
                        FROM
                            -- only select the latest row
                            (
                                SELECT DISTINCT ON (flow_run_id)
                                    id,
                                    version,
                                    flow_run_id,
                                    state,
                                    serialized_state,
                                    start_time,
                                    timestamp,
                                    message,
                                    result
                                FROM new_state
                                ORDER BY flow_run_id, version DESC, timestamp DESC
                            ) AS new_latest_state
                        WHERE
                            new_latest_state.flow_run_id = flow_run.id
                            AND (
                                flow_run.version IS NULL
                                OR (
                                    new_latest_state.version >= COALESCE(flow_run.version, -1)
                                    AND new_latest_state.timestamp > COALESCE(flow_run.state_timestamp, '2000-01-01')));
                        RETURN NEW;
                    END;
                    $$;


        CREATE FUNCTION update_task_run_with_latest_state() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
                    BEGIN
                        UPDATE task_run
                        SET
                            version = new_latest_state.version,
                            -- below are fields that we only include for backwards-compatibility
                            state=new_latest_state.state,
                            serialized_state=new_latest_state.serialized_state,
                            state_start_time=new_latest_state.start_time,
                            state_timestamp=new_latest_state.timestamp,
                            state_message=new_latest_state.message,
                            state_result=new_latest_state.result
                        FROM
                            -- only select the latest row
                            (
                                SELECT DISTINCT ON (task_run_id)
                                    id,
                                    version,
                                    task_run_id,
                                    state,
                                    serialized_state,
                                    start_time,
                                    timestamp,
                                    message,
                                    result
                                FROM new_state
                                ORDER BY task_run_id, version DESC, timestamp DESC
                            ) AS new_latest_state
                        WHERE
                            new_latest_state.task_run_id = task_run.id
                            AND (
                                task_run.version IS NULL
                                OR (
                                    new_latest_state.version >= COALESCE(task_run.version, -1)
                                    AND new_latest_state.timestamp > COALESCE(task_run.state_timestamp, '2000-01-01')));
                        RETURN NEW;
                    END;
                    $$;

            CREATE TRIGGER update_flow_run_after_inserting_state
            AFTER INSERT ON flow_run_state
            REFERENCING NEW TABLE AS new_state
            FOR EACH STATEMENT
            EXECUTE PROCEDURE update_flow_run_with_latest_state();

            CREATE TRIGGER update_task_run_after_inserting_state
            AFTER INSERT ON task_run_state
            REFERENCING NEW TABLE AS new_state
            FOR EACH STATEMENT
            EXECUTE PROCEDURE update_task_run_with_latest_state();
            """
    )

    op.drop_column("flow_run", "state_id")
    op.drop_column("task_run", "state_id")


def downgrade():
    op.add_column(
        "flow_run",
        sa.Column(
            "state_id", UUID, sa.ForeignKey("flow_run_state.id", ondelete="SET NULL")
        ),
    )
    op.add_column(
        "task_run",
        sa.Column(
            "state_id", UUID, sa.ForeignKey("task_run_state.id", ondelete="SET NULL")
        ),
    )
    op.execute(
        """
        CREATE INDEX ix_flow_run__state_id ON flow_run USING btree (state_id);
        CREATE INDEX ix_task_run__state_id ON task_run USING btree (state_id);
        """
    )

    op.execute(
        """
        DROP FUNCTION update_flow_run_with_latest_state CASCADE;
        DROP FUNCTION update_task_run_with_latest_state CASCADE;
        """
    )
    op.execute(
        """
        CREATE FUNCTION update_flow_run_with_latest_state() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
                    BEGIN
                        UPDATE flow_run
                        SET
                            version = new_latest_state.version,
                            state_id = new_latest_state.id,
                            -- below are fields that we only include for backwards-compatibility
                            state=new_latest_state.state,
                            serialized_state=new_latest_state.serialized_state,
                            state_start_time=new_latest_state.start_time,
                            state_timestamp=new_latest_state.timestamp,
                            state_message=new_latest_state.message,
                            state_result=new_latest_state.result
                        FROM
                            -- only select the latest row
                            (
                                SELECT DISTINCT ON (flow_run_id)
                                    id,
                                    version,
                                    flow_run_id,
                                    state,
                                    serialized_state,
                                    start_time,
                                    timestamp,
                                    message,
                                    result
                                FROM new_state
                                ORDER BY flow_run_id, version DESC, timestamp DESC
                            ) AS new_latest_state
                        WHERE
                            new_latest_state.flow_run_id = flow_run.id
                            AND (
                                flow_run.version IS NULL
                                OR (
                                    new_latest_state.version >= COALESCE(flow_run.version, -1)
                                    AND new_latest_state.timestamp > COALESCE(flow_run.state_timestamp, '2000-01-01')));
                        RETURN NEW;
                    END;
                    $$;


        CREATE FUNCTION update_task_run_with_latest_state() RETURNS trigger
            LANGUAGE plpgsql
            AS $$
                    BEGIN
                        UPDATE task_run
                        SET
                            version = new_latest_state.version,
                            state_id = new_latest_state.id,
                            -- below are fields that we only include for backwards-compatibility
                            state=new_latest_state.state,
                            serialized_state=new_latest_state.serialized_state,
                            state_start_time=new_latest_state.start_time,
                            state_timestamp=new_latest_state.timestamp,
                            state_message=new_latest_state.message,
                            state_result=new_latest_state.result
                        FROM
                            -- only select the latest row
                            (
                                SELECT DISTINCT ON (task_run_id)
                                    id,
                                    version,
                                    task_run_id,
                                    state,
                                    serialized_state,
                                    start_time,
                                    timestamp,
                                    message,
                                    result
                                FROM new_state
                                ORDER BY task_run_id, version DESC, timestamp DESC
                            ) AS new_latest_state
                        WHERE
                            new_latest_state.task_run_id = task_run.id
                            AND (
                                task_run.version IS NULL
                                OR (
                                    new_latest_state.version >= COALESCE(task_run.version, -1)
                                    AND new_latest_state.timestamp > COALESCE(task_run.state_timestamp, '2000-01-01')));
                        RETURN NEW;
                    END;
                    $$;

            CREATE TRIGGER update_flow_run_after_inserting_state
            AFTER INSERT ON flow_run_state
            REFERENCING NEW TABLE AS new_state
            FOR EACH STATEMENT
            EXECUTE PROCEDURE update_flow_run_with_latest_state();

            CREATE TRIGGER update_task_run_after_inserting_state
            AFTER INSERT ON task_run_state
            REFERENCING NEW TABLE AS new_state
            FOR EACH STATEMENT
            EXECUTE PROCEDURE update_task_run_with_latest_state();
            """
    )
