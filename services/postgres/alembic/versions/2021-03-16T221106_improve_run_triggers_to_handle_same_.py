"""
Improve run triggers to handle same-version states

Revision ID: 459a61bedc9e
Revises: 9116e81c6dc2
Create Date: 2021-03-16 22:11:06.618713

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "459a61bedc9e"
down_revision = "9116e81c6dc2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP FUNCTION update_flow_run_details_on_state_insert CASCADE;
        DROP FUNCTION update_task_run_details_on_state_insert CASCADE;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_flow_run_details_on_state_insert()
            RETURNS TRIGGER AS $$
            	BEGIN
            	    UPDATE flow_run
            	    SET 
            	    	start_time = CASE WHEN NEW.version >= COALESCE(version, 0) AND NEW.state = 'Running' THEN LEAST(start_time, NEW.timestamp) ELSE start_time END,
            	    	end_time = CASE WHEN NEW.version >= COALESCE(version, 0) AND NEW.state in ('Success', 'Failed', 'Cached', 'TimedOut', 'Looped', 'Cancelled') THEN GREATEST(end_time, NEW.timestamp) ELSE end_time END,
            	    	version = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.version ELSE version END,
        	            state = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.state ELSE state END,
             	        serialized_state = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.serialized_state ELSE serialized_state END,
  	            	    state_start_time = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.start_time ELSE state_start_time END,
    	                state_timestamp = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.timestamp ELSE state_timestamp END,
        	            state_message = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.message ELSE state_message END,
            	        state_result = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.result ELSE state_result END
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
            	    	start_time = CASE WHEN NEW.version >= COALESCE(version, 0) AND NEW.state = 'Running' THEN LEAST(start_time, NEW.timestamp) ELSE start_time END,
            	    	end_time = CASE WHEN NEW.version >= COALESCE(version, 0) AND NEW.state in ('Success', 'Failed', 'Cached', 'TimedOut', 'Looped', 'Cancelled') THEN GREATEST(end_time, NEW.timestamp) ELSE end_time END,
            	    	version = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.version ELSE version END,
        	            state = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.state ELSE state END,
             	        serialized_state = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.serialized_state ELSE serialized_state END,
  	            	    state_start_time = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.start_time ELSE state_start_time END,
    	                state_timestamp = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.timestamp ELSE state_timestamp END,
        	            state_message = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.message ELSE state_message END,
            	        state_result = CASE WHEN NEW.version >= COALESCE(version, 0) THEN NEW.result ELSE state_result END
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


def downgrade():
    op.execute(
        """
        DROP FUNCTION update_flow_run_details_on_state_insert CASCADE;
        DROP FUNCTION update_task_run_details_on_state_insert CASCADE;
        """
    )
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
