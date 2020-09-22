"""
Simplify run state update triggers

Revision ID: 6611fd0ccc73
Revises: c1f317aa658c
Create Date: 2020-09-02 20:34:35.380023

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "6611fd0ccc73"
down_revision = "c1f317aa658c"
branch_labels = None
depends_on = None


def upgrade():
    # drop old trigger functions
    op.execute(
        """
        drop function update_flow_run_with_timing_details CASCADE;
        drop function update_flow_run_with_latest_state CASCADE;
        drop function update_task_run_with_timing_details CASCADE;
        drop function update_task_run_with_latest_state CASCADE;
        """
    )

    # create new trigger functions
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_flow_run_details_on_state_insert()
            RETURNS TRIGGER AS $$
            	BEGIN
            	    UPDATE flow_run
            	    SET 
            	    	start_time = CASE WHEN NEW.version > version AND NEW.state = 'Running' THEN LEAST(start_time, NEW.timestamp) ELSE start_time END,
            	    	end_time = CASE WHEN NEW.version > version AND NEW.state in ('Success', 'Failed', 'Cached', 'TimedOut', 'Looped', 'Cancelled') THEN GREATEST(end_time, NEW.timestamp) ELSE end_time END,
            	    	version = CASE WHEN NEW.version > version THEN NEW.version ELSE version END,
        	            state = CASE WHEN NEW.version > version THEN NEW.state ELSE state END,
             	        serialized_state = CASE WHEN NEW.version > version THEN NEW.serialized_state ELSE serialized_state END,
  	            	    state_start_time = CASE WHEN NEW.version > version THEN NEW.start_time ELSE state_start_time END,
    	                state_timestamp = CASE WHEN NEW.version > version THEN NEW.timestamp ELSE state_timestamp END,
        	            state_message = CASE WHEN NEW.version > version THEN NEW.message ELSE state_message END,
            	        state_result = CASE WHEN NEW.version > version THEN NEW.result ELSE state_result END
            	    WHERE id = NEW.flow_run_id;
            	    RETURN NEW;
            	END;
            
            $$
            LANGUAGE plpgsql;

        CREATE OR REPLACE FUNCTION update_task_run_details_on_state_insert()
            RETURNS TRIGGER AS $$
            	BEGIN
            	    UPDATE task_run
            	    SET 
            	    	start_time = CASE WHEN NEW.version > version AND NEW.state = 'Running' THEN LEAST(start_time, NEW.timestamp) ELSE start_time END,
            	    	end_time = CASE WHEN NEW.version > version AND NEW.state in ('Success', 'Failed', 'Cached', 'TimedOut', 'Looped', 'Cancelled') THEN GREATEST(end_time, NEW.timestamp) ELSE end_time END,
            	    	version = CASE WHEN NEW.version > version THEN NEW.version ELSE version END,
        	            state = CASE WHEN NEW.version > version THEN NEW.state ELSE state END,
             	        serialized_state = CASE WHEN NEW.version > version THEN NEW.serialized_state ELSE serialized_state END,
  	            	    state_start_time = CASE WHEN NEW.version > version THEN NEW.start_time ELSE state_start_time END,
    	                state_timestamp = CASE WHEN NEW.version > version THEN NEW.timestamp ELSE state_timestamp END,
        	            state_message = CASE WHEN NEW.version > version THEN NEW.message ELSE state_message END,
            	        state_result = CASE WHEN NEW.version > version THEN NEW.result ELSE state_result END
            	    WHERE id = NEW.task_run_id;
            	    RETURN NEW;
            	END;
            
            $$
            LANGUAGE plpgsql;
        """
    )

    # create triggers
    op.execute(
        """
        CREATE TRIGGER update_flow_run_details_on_state_insert
        AFTER INSERT ON flow_run_state
        FOR EACH ROW
        EXECUTE PROCEDURE update_flow_run_details_on_state_insert();


        CREATE TRIGGER update_task_run_details_on_state_insert
        AFTER INSERT ON task_run_state
        FOR EACH ROW
        EXECUTE PROCEDURE update_task_run_details_on_state_insert();
        """
    )

    # drop columns
    op.drop_column("flow_run", "duration")
    op.drop_column("task_run", "run_count")
    op.drop_column("task_run", "duration")

    # change state version to default to 1
    # this will ensure that newly-written states overwrite the parent run
    op.alter_column("flow_run_state", "version", server_default="1")
    op.alter_column("task_run_state", "version", server_default="1")


def downgrade():

    op.add_column(
        "flow_run", sa.Column("duration", sa.Interval),
    )
    op.add_column(
        "task_run", sa.Column("duration", sa.Interval),
    )
    op.add_column(
        "task_run",
        sa.Column("run_count", sa.Integer, nullable=False, server_default="0"),
    )

    op.execute(
        """
        DROP FUNCTION update_flow_run_details_on_state_insert CASCADE;
        DROP FUNCTION update_task_run_details_on_state_insert CASCADE;
        """
    )

    op.execute(
        """
        -- trigger to update flow runs when flow run states are inserted
        -- note: these triggers consider the minimum and maximum timestamps from all valid
        -- RUNNING states and the states that immediately follow them.

        CREATE FUNCTION update_flow_run_with_timing_details() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE flow_run
                SET
                    start_time = run_details.start_time,
                    end_time = run_details.end_time,
                    duration = run_details.duration
                FROM (
                    SELECT
                        flow_run_id,
                        min(start_timestamp) AS start_time,
                        max(end_timestamp) AS end_time,
                        max(end_timestamp) - min(start_timestamp) AS duration
                    FROM (
                        SELECT
                            id,
                            flow_run_id,
                            state,
                            timestamp AS start_timestamp,

                            -- order by version AND timestamp to break ties for old states that don't have versions
                            LEAD(timestamp) OVER (PARTITION BY flow_run_id ORDER BY version, timestamp) AS end_timestamp

                        FROM
                            flow_run_state
                        WHERE flow_run_id in (SELECT flow_run_id FROM new_state)
                        ) ts
                    WHERE
                        state = 'Running'
                    GROUP BY flow_run_id
                    ORDER BY flow_run_id
                ) run_details
                WHERE run_details.flow_run_id = flow_run.id;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;



        -- trigger to update task runs when task run states are inserted
        -- note: these triggers consider the minimum and maximum timestamps from all valid
        -- RUNNING states and the states that immediately follow them.

        CREATE FUNCTION update_task_run_with_timing_details() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE task_run
                SET
                    start_time = run_details.start_time,
                    end_time = run_details.end_time,
                    duration = run_details.duration,
                    run_count = run_details.run_count
                FROM (
                    SELECT
                        task_run_id,

                        -- start time, end time, and duartion are all computed from running states
                        min(start_timestamp) FILTER (WHERE state = 'Running') AS start_time,
                        max(end_timestamp) FILTER (WHERE state = 'Running') AS end_time,
                        max(end_timestamp) FILTER (WHERE state = 'Running') - min(start_timestamp) FILTER (WHERE state = 'Running') AS duration,

                        -- run count needs to subtract looped states
                        count(*) FILTER (WHERE state = 'Running') - count(*) FILTER (WHERE state = 'Looped') AS run_count
                    FROM (
                        SELECT
                            id,
                            task_run_id,
                            state,
                            timestamp AS start_timestamp,

                            -- order by version AND timestamp to break ties for old states that don't have versions
                            LEAD(timestamp) OVER (PARTITION BY task_run_id ORDER BY version, timestamp) AS end_timestamp

                        FROM
                            task_run_state
                        WHERE task_run_id in (SELECT task_run_id FROM new_state)
                        ) ts
                    WHERE
                        state in ('Running', 'Looped')
                    GROUP BY task_run_id
                    ORDER BY task_run_id
                ) run_details
                WHERE run_details.task_run_id = task_run.id;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

        CREATE TRIGGER update_flow_run_timing_details_after_inserting_state
        AFTER INSERT ON flow_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_flow_run_with_timing_details();

        CREATE TRIGGER update_task_run_timing_details_after_inserting_state
        AFTER INSERT ON task_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_task_run_with_timing_details();

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

    op.alter_column("flow_run_state", "version", server_default="0")
    op.alter_column("task_run_state", "version", server_default="0")
