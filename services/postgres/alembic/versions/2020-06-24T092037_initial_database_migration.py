"""
Initial database tables migration

Revision ID: 72e2cd3e0469
Revises: 27811b58307b
Create Date: 2020-06-24 09:20:37.941466

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "72e2cd3e0469"
down_revision = "27811b58307b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    CREATE FUNCTION public.insert_task_runs_after_flow_run_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                -- create task runs for each of the tasks in the new flow run's
                -- flow
                INSERT INTO task_run (tenant_id, flow_run_id, task_id, cache_key, map_index)
                SELECT NEW.tenant_id, NEW.id, task.id, task.cache_key, -1
                FROM task
                WHERE task.flow_id = NEW.flow_id;
                -- create corresponding states for each of the new task runs
                INSERT INTO task_run_state(tenant_id, task_run_id, state, message, serialized_state)
                SELECT NEW.tenant_id, task_run.id, 'Pending', 'Task run created', '{"type": "Pending", "message": "Task run created"}'
                FROM task_run
                WHERE task_run.flow_run_id = NEW.id;
            RETURN NEW;
            END;
            $$;
CREATE FUNCTION public.set_updated_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.updated = NOW();
            RETURN NEW;
        END;
        $$;
CREATE FUNCTION public.update_flow_run_with_latest_state() RETURNS trigger
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
CREATE FUNCTION public.update_flow_run_with_timing_details() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
            $$;
CREATE FUNCTION public.update_task_run_with_latest_state() RETURNS trigger
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
CREATE FUNCTION public.update_task_run_with_timing_details() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
            $$;
            """
    )
    op.execute(
        """
CREATE TABLE public.tenant (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    created timestamp with time zone DEFAULT now() NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    info jsonb,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.cloud_hook (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    name character varying,
    states jsonb,
    type character varying NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    active boolean DEFAULT true NOT NULL,
    version_group_id character varying
);
CREATE TABLE public.edge (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    flow_id uuid NOT NULL,
    upstream_task_id uuid NOT NULL,
    downstream_task_id uuid NOT NULL,
    key character varying,
    mapped boolean DEFAULT false NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.flow (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    version integer,
    name character varying NOT NULL,
    description character varying,
    environment jsonb,
    parameters jsonb DEFAULT '{}'::jsonb,
    project_id uuid NOT NULL,
    archived boolean DEFAULT false NOT NULL,
    version_group_id character varying,
    storage jsonb,
    core_version character varying,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    serialized_flow jsonb,
    schedule jsonb,
    is_schedule_active boolean DEFAULT false NOT NULL,
    flow_group_id uuid NOT NULL
);
CREATE TABLE public.flow_group (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    name character varying,
    labels JSONB,
    schedule JSONB,
    settings jsonb DEFAULT '{}'::jsonb NOT NULL,
    default_parameters jsonb DEFAULT '{}'::jsonb NOT NULL
);
CREATE TABLE public.flow_run (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    flow_id uuid NOT NULL,
    parameters jsonb DEFAULT '{}'::jsonb,
    scheduled_start_time timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    auto_scheduled boolean DEFAULT false NOT NULL,
    heartbeat timestamp with time zone,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    duration interval,
    version integer DEFAULT 0 NOT NULL,
    state character varying,
    state_timestamp timestamp with time zone,
    state_message character varying,
    state_result jsonb,
    state_start_time timestamp with time zone,
    serialized_state jsonb,
    name character varying,
    context jsonb,
    times_resurrected integer DEFAULT 0,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    state_id uuid
);
CREATE TABLE public.flow_run_state (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    flow_run_id uuid NOT NULL,
    "timestamp" timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    state character varying NOT NULL,
    message character varying,
    result jsonb,
    start_time timestamp with time zone,
    serialized_state jsonb NOT NULL,
    created timestamp with time zone DEFAULT now() NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 0
);
CREATE TABLE public.log (
    flow_run_id uuid,
    tenant_id uuid,
    task_run_id uuid,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    name character varying,
    level character varying,
    message character varying,
    info jsonb,
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    created timestamp with time zone DEFAULT now() NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    is_loaded_from_archive boolean
);
CREATE TABLE public.project (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    name character varying NOT NULL,
    description character varying,
    updated timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.task (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    flow_id uuid NOT NULL,
    name character varying,
    slug character varying,
    description character varying,
    type character varying,
    max_retries integer,
    retry_delay interval,
    trigger character varying,
    mapped boolean DEFAULT false NOT NULL,
    auto_generated boolean DEFAULT false NOT NULL,
    cache_key character varying,
    is_root_task boolean DEFAULT false NOT NULL,
    is_terminal_task boolean DEFAULT false NOT NULL,
    is_reference_task boolean DEFAULT false NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE public.task_run (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    created timestamp with time zone DEFAULT now() NOT NULL,
    flow_run_id uuid NOT NULL,
    task_id uuid NOT NULL,
    map_index integer DEFAULT '-1'::integer NOT NULL,
    version integer DEFAULT 0 NOT NULL,
    heartbeat timestamp with time zone,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    duration interval,
    run_count integer DEFAULT 0 NOT NULL,
    state character varying,
    state_timestamp timestamp with time zone,
    state_message character varying,
    state_result jsonb,
    state_start_time timestamp with time zone,
    serialized_state jsonb,
    cache_key character varying,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    state_id uuid
);
CREATE TABLE public.task_run_state (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    tenant_id uuid,
    task_run_id uuid NOT NULL,
    "timestamp" timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    state character varying NOT NULL,
    message character varying,
    result jsonb,
    start_time timestamp with time zone,
    serialized_state jsonb NOT NULL,
    created timestamp with time zone DEFAULT now() NOT NULL,
    updated timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 0
);
    """
    )
    op.execute(
        """
ALTER TABLE ONLY public.cloud_hook
    ADD CONSTRAINT cloud_hook_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.edge
    ADD CONSTRAINT edge_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.flow_group
    ADD CONSTRAINT flow_group_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.flow_run
    ADD CONSTRAINT flow_run_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.flow_run_state
    ADD CONSTRAINT flow_run_state_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_tenant_id_name_key UNIQUE (tenant_id, name);
ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_flow_id_slug_key UNIQUE (flow_id, slug);
ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT task_run_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.task_run_state
    ADD CONSTRAINT task_run_state_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT task_run_unique_identifier_key UNIQUE (flow_run_id, task_id, map_index);
ALTER TABLE ONLY public.tenant
    ADD CONSTRAINT tenant_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.tenant
    ADD CONSTRAINT tenant_slug_key UNIQUE (slug);


            """
    )
    op.execute(
        """
CREATE INDEX ix_cloud_hook_tenant_id ON public.cloud_hook USING btree (tenant_id);
CREATE INDEX ix_cloud_hook_states ON public.cloud_hook USING gin (states);
CREATE INDEX ix_cloud_hook_type ON public.cloud_hook USING btree (type);
CREATE INDEX ix_cloud_hook_updated ON public.cloud_hook USING btree (updated);
CREATE INDEX ix_cloud_hook_version_group_id ON public.cloud_hook USING btree (version_group_id);
CREATE INDEX ix_edge_tenant_id ON public.edge USING btree (tenant_id);
CREATE INDEX ix_edge_downstream_task_id ON public.edge USING btree (downstream_task_id);
CREATE INDEX ix_edge_flow_id ON public.edge USING btree (flow_id);
CREATE INDEX ix_edge_updated ON public.edge USING btree (updated);
CREATE INDEX ix_edge_upstream_task_id ON public.edge USING btree (upstream_task_id);
CREATE INDEX ix_flow_tenant_id ON public.flow USING btree (tenant_id);
CREATE INDEX ix_flow_flow_group_id ON public.flow USING btree (flow_group_id);
CREATE INDEX ix_flow_name ON public.flow USING gin (name public.gin_trgm_ops);
CREATE INDEX ix_flow_project_id ON public.flow USING btree (project_id);
CREATE INDEX ix_flow_group_tenant_id ON public.flow_group USING btree (tenant_id);
CREATE INDEX ix_flow_run_tenant_id ON public.flow_run USING btree (tenant_id);
CREATE INDEX ix_flow_run__state_id ON public.flow_run USING btree (state_id);
CREATE INDEX ix_flow_run_flow_id ON public.flow_run USING btree (flow_id);
CREATE INDEX ix_flow_run_flow_id_scheduled_start_time_for_hasura ON public.flow_run USING btree (flow_id, scheduled_start_time DESC);
CREATE INDEX ix_flow_run_heartbeat ON public.flow_run USING btree (heartbeat);
CREATE INDEX ix_flow_run_name ON public.flow_run USING gin (name public.gin_trgm_ops);
CREATE INDEX ix_flow_run_scheduled_start_time ON public.flow_run USING btree (scheduled_start_time);
CREATE INDEX ix_flow_run_start_time ON public.flow_run USING btree (start_time);
CREATE INDEX ix_flow_run_state_tenant_id ON public.flow_run_state USING btree (tenant_id);
CREATE INDEX ix_flow_run_state ON public.flow_run USING btree (state);
CREATE INDEX ix_flow_run_state_flow_run_id ON public.flow_run_state USING btree (flow_run_id);
CREATE INDEX ix_flow_run_state_state ON public.flow_run_state USING btree (state);
CREATE INDEX ix_flow_run_state_timestamp ON public.flow_run_state USING btree ("timestamp");
CREATE INDEX ix_flow_run_state_updated ON public.flow_run_state USING btree (updated);
CREATE INDEX ix_flow_run_updated ON public.flow_run USING btree (updated);
CREATE INDEX ix_flow_updated ON public.flow USING btree (updated);
CREATE INDEX ix_flow_version ON public.flow USING btree (version);
CREATE INDEX ix_flow_version_group_id ON public.flow USING btree (version_group_id);
CREATE INDEX ix_log_tenant_id ON public.log USING btree (tenant_id);
CREATE INDEX ix_log_flow_run_id ON public.log USING btree (flow_run_id);
CREATE INDEX ix_log_task_run_id ON public.log USING btree (task_run_id);
CREATE INDEX ix_log_updated ON public.log USING btree (updated);
CREATE INDEX ix_project_tenant_id ON public.project USING btree (tenant_id);
CREATE INDEX ix_project_name ON public.project USING gin (name public.gin_trgm_ops);
CREATE INDEX ix_project_updated ON public.project USING btree (updated);
CREATE INDEX ix_task_tenant_id ON public.task USING btree (tenant_id);
CREATE INDEX ix_task_flow_id ON public.task USING btree (flow_id);
CREATE INDEX ix_task_name ON public.task USING gin (name public.gin_trgm_ops);
CREATE INDEX ix_task_run_tenant_id ON public.task_run USING btree (tenant_id);
CREATE INDEX ix_task_run__state_id ON public.task_run USING btree (state_id);
CREATE INDEX ix_task_run_cache_key ON public.task_run USING btree (cache_key);
CREATE INDEX ix_task_run_flow_run_id ON public.task_run USING btree (flow_run_id);
CREATE INDEX ix_task_run_heartbeat ON public.task_run USING btree (heartbeat);
CREATE INDEX ix_task_run_state_tenant_id ON public.task_run_state USING btree (tenant_id);
CREATE INDEX ix_task_run_state ON public.task_run USING btree (state);
CREATE INDEX ix_task_run_state_state ON public.task_run_state USING btree (state);
CREATE INDEX ix_task_run_state_task_run_id ON public.task_run_state USING btree (task_run_id);
CREATE INDEX ix_task_run_state_timestamp ON public.task_run_state USING btree ("timestamp");
CREATE INDEX ix_task_run_state_updated ON public.task_run_state USING btree (updated);
CREATE INDEX ix_task_run_task_id ON public.task_run USING btree (task_id);
CREATE INDEX ix_task_run_updated ON public.task_run USING btree (updated);
CREATE INDEX ix_task_tags ON public.task USING gin (tags);
CREATE INDEX ix_task_updated ON public.task USING btree (updated);
CREATE TRIGGER insert_task_runs_after_flow_run_insert AFTER INSERT ON public.flow_run FOR EACH ROW EXECUTE PROCEDURE public.insert_task_runs_after_flow_run_insert();
CREATE TRIGGER update_flow_run_after_inserting_state AFTER INSERT ON public.flow_run_state REFERENCING NEW TABLE AS new_state FOR EACH STATEMENT EXECUTE PROCEDURE public.update_flow_run_with_latest_state();
CREATE TRIGGER update_flow_run_timing_details_after_inserting_state AFTER INSERT ON public.flow_run_state REFERENCING NEW TABLE AS new_state FOR EACH STATEMENT EXECUTE PROCEDURE public.update_flow_run_with_timing_details();
CREATE TRIGGER update_task_run_after_inserting_state AFTER INSERT ON public.task_run_state REFERENCING NEW TABLE AS new_state FOR EACH STATEMENT EXECUTE PROCEDURE public.update_task_run_with_latest_state();
CREATE TRIGGER update_task_run_timing_details_after_inserting_state AFTER INSERT ON public.task_run_state REFERENCING NEW TABLE AS new_state FOR EACH STATEMENT EXECUTE PROCEDURE public.update_task_run_with_timing_details();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.cloud_hook FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.edge FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.flow FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.flow_group FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.flow_run FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.flow_run_state FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.log FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.project FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.task FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.task_run FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.task_run_state FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();
CREATE TRIGGER update_timestamp BEFORE UPDATE ON public.tenant FOR EACH ROW EXECUTE PROCEDURE public.set_updated_timestamp();

            """
    )
    op.execute(
        """
ALTER TABLE ONLY public.cloud_hook
    ADD CONSTRAINT cloud_hook_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.edge
    ADD CONSTRAINT fk_edge_downstream_task_id FOREIGN KEY (downstream_task_id) REFERENCES public.task(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.edge
    ADD CONSTRAINT fk_edge_flow_id FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.edge
    ADD CONSTRAINT fk_edge_upstream_task_id FOREIGN KEY (upstream_task_id) REFERENCES public.task(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.edge
    ADD CONSTRAINT edge_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_flow_group_id_fkey FOREIGN KEY (flow_group_id) REFERENCES public.flow_group(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_group
    ADD CONSTRAINT flow_group_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_run
    ADD CONSTRAINT fk_flow_run_flow_id FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_run
    ADD CONSTRAINT flow_run_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_run_state
    ADD CONSTRAINT flow_run_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task
    ADD CONSTRAINT fk_task_flow_id FOREIGN KEY (flow_id) REFERENCES public.flow(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task
    ADD CONSTRAINT task_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT fk_task_run_flow_run_id FOREIGN KEY (flow_run_id) REFERENCES public.flow_run(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT task_run_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.project
    ADD CONSTRAINT project_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT fk_task_run_task_id FOREIGN KEY (task_id) REFERENCES public.task(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow
    ADD CONSTRAINT flow_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.project(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_run_state
    ADD CONSTRAINT flow_run_state_flow_run_id_fkey FOREIGN KEY (flow_run_id) REFERENCES public.flow_run(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.flow_run
    ADD CONSTRAINT flow_run_state_id_fkey FOREIGN KEY (state_id) REFERENCES public.flow_run_state(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.task_run
    ADD CONSTRAINT task_run_state_id_fkey FOREIGN KEY (state_id) REFERENCES public.task_run_state(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.task_run_state
    ADD CONSTRAINT task_run_state_tmp_table_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_run(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.task_run_state
    ADD CONSTRAINT task_run_state_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.log
    ADD CONSTRAINT log_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.log
    ADD CONSTRAINT log_flow_run_id_fkey FOREIGN KEY (flow_run_id) REFERENCES public.flow_run(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.log
    ADD CONSTRAINT log_task_run_id_fkey FOREIGN KEY (task_run_id) REFERENCES public.task_run(id) ON DELETE CASCADE;

        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE public.cloud_hook CASCADE;
        DROP TABLE public.edge CASCADE;
        DROP TABLE public.flow CASCADE;
        DROP TABLE public.flow_group CASCADE;
        DROP TABLE public.flow_run CASCADE;
        DROP TABLE public.flow_run_state CASCADE;
        DROP TABLE public.log CASCADE;
        DROP TABLE public.project CASCADE;
        DROP TABLE public.task CASCADE;
        DROP TABLE public.task_run CASCADE;
        DROP TABLE public.task_run_state CASCADE;
        DROP TABLE public.tenant CASCADE;
        """
    )

    op.execute(
        """
        DROP FUNCTION public.insert_task_runs_after_flow_run_insert;
        DROP FUNCTION public.set_updated_timestamp;
        DROP FUNCTION public.update_flow_run_with_latest_state;
        DROP FUNCTION public.update_flow_run_with_timing_details;
        DROP FUNCTION public.update_task_run_with_latest_state;
        DROP FUNCTION public.update_task_run_with_timing_details;
        """
    )
