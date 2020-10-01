import asyncio
import uuid

import pendulum
import pytest

import prefect
from prefect import api, models
from prefect.engine.state import Pending, Scheduled


class TestCreateFlowRun:
    mutation = """
        mutation($input: create_flow_run_input!) {
            create_flow_run(input: $input) {
                id
            }
        }
    """

    async def test_create_flow_run(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
                "labels",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.labels == []
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}

    async def test_create_flow_run_with_labels(self, run_query, flow_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    labels=["a", "b", "c"],
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "labels",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.labels == ["a", "b", "c"]

    async def test_create_flow_run_with_version_group_id(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        f = await models.Flow.where(id=flow_id).first({"version_group_id"})
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=None,
                    version_group_id=f.version_group_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}

    async def test_create_flow_run_with_run_name(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                    flow_run_name="named flow run",
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
                "name",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}
        assert fr.name == "named flow run"

    async def test_create_flow_run_fails_for_archived_flow(self, run_query, flow_id):
        await api.flows.archive_flow(flow_id)
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, parameters=dict(x=1))),
        )
        assert "archived" in result.errors[0].message

    async def test_create_flow_run_without_parameters_raises_error(
        self, run_query, project_id
    ):

        serialized_flow = prefect.Flow(
            name="test", tasks=[prefect.Parameter("x")]
        ).serialize(build=False)
        create_flow_mutation = """
            mutation($input: create_flow_input!) {
                create_flow(input: $input) {
                    id
                }
            }
        """
        result = await run_query(
            query=create_flow_mutation,
            variables=dict(
                input=dict(project_id=project_id, serialized_flow=serialized_flow)
            ),
        )

        pendulum.now("utc")
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=result.data.create_flow.id)),
        )
        assert result.data.create_flow_run is None
        assert "Required parameters" in result.errors[0].message


class TestGetOrCreateTaskRun:
    mutation = """
        mutation($input: get_or_create_task_run_input!) {
            get_or_create_task_run(input: $input) {
                id
            }
        }
    """

    async def test_get_or_create_task_run(
        self, run_query, task_run_id, task_id, flow_run_id
    ):
        n_tr = await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id, task_id=task_id)),
        )

        assert result.data.get_or_create_task_run.id == task_run_id
        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == n_tr
        )

    async def test_get_or_create_task_run_new_task_run(
        self, run_query, task_run_id, task_id, flow_run_id
    ):
        n_tr = await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(flow_run_id=flow_run_id, task_id=task_id, map_index=10)
            ),
        )

        assert result.data.get_or_create_task_run.id != task_run_id
        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == n_tr + 1
        )


class TestGetOrCreateMappedTaskRunChildren:
    mutation = """
        mutation($input: get_or_create_mapped_task_run_children_input!) {
            get_or_create_mapped_task_run_children(input: $input) {
                ids
            }
        }
    """

    async def test_get_or_create_mapped_task_run_children(
        self, run_query, flow_run_id, flow_id
    ):
        # grab the task ID
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first({"id"})
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(flow_run_id=flow_run_id, task_id=task.id, max_map_index=5)
            ),
        )
        # should have 6 children, indices 0-5
        assert len(result.data.get_or_create_mapped_task_run_children.ids) == 6

    async def test_get_or_create_mapped_task_run_children_with_partial_children(
        self, run_query, flow_run_id, flow_id
    ):
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first({"id"})
        # create a couple of children
        preexisting_run_1 = await models.TaskRun(
            flow_run_id=flow_run_id,
            task_id=task.id,
            map_index=3,
            cache_key=task.cache_key,
        ).insert()
        preexisting_run_2 = await models.TaskRun(
            flow_run_id=flow_run_id,
            task_id=task.id,
            map_index=6,
            cache_key=task.cache_key,
            states=[
                models.TaskRunState(
                    **models.TaskRunState.fields_from_state(
                        Pending(message="Task run created")
                    ),
                )
            ],
        ).insert()
        # call the route
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(flow_run_id=flow_run_id, task_id=task.id, max_map_index=10)
            ),
        )
        mapped_children = result.data.get_or_create_mapped_task_run_children.ids
        # should have 11 children, indices 0-10
        assert len(mapped_children) == 11

        # confirm the preexisting task runs were included in the results
        assert preexisting_run_1 in mapped_children
        assert preexisting_run_2 in mapped_children

        # confirm the results are ordered
        map_indices = []
        for child in mapped_children:
            map_indices.append(
                (await models.TaskRun.where(id=child).first({"map_index"})).map_index
            )
        assert map_indices == sorted(map_indices)


class TestUpdateFlowRunHeartbeat:
    mutation = """
        mutation($input: update_flow_run_heartbeat_input!) {
            update_flow_run_heartbeat(input: $input) {
                success
            }
        }
    """

    async def test_update_flow_run_heartbeat(self, run_query, flow_run_id):
        dt = pendulum.now()
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id)),
        )

        # sleep to give the concurrent update a chance to run
        await asyncio.sleep(0.1)
        run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})

        assert result.data.update_flow_run_heartbeat.success
        assert dt < run.heartbeat

    async def test_update_flow_run_heartbeat_invalid_id_returns_success(
        self, run_query
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=str(uuid.uuid4()))),
        )

        assert result.data.update_flow_run_heartbeat.success


class TestUpdateTaskRunHeartbeat:
    mutation = """
        mutation($input: update_task_run_heartbeat_input!) {
            update_task_run_heartbeat(input: $input) {
                success
            }
        }
    """

    async def test_update_task_run_heartbeat(self, run_query, task_run_id):
        dt = pendulum.now()
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(task_run_id=task_run_id)),
        )

        # sleep to give the concurrent update a chance to run
        await asyncio.sleep(0.1)
        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})

        assert result.data.update_task_run_heartbeat.success
        assert dt < run.heartbeat

    async def test_update_task_run_heartbeat_invalid_id_is_still_success(
        self, run_query
    ):
        pendulum.now()
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(task_run_id=str(uuid.uuid4()))),
        )

        assert result.data.update_task_run_heartbeat.success


class TestDeleteFlowRun:
    mutation = """
        mutation($input: delete_flow_run_input!) {
            delete_flow_run(input: $input) {
                success
            }
        }
    """

    async def test_delete_flow_run(self, run_query, flow_run_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id)),
        )

        assert result.data.delete_flow_run.success
        assert not await models.FlowRun.exists(flow_run_id)

    async def test_delete_flow_run_bad_id(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=str(uuid.uuid4()))),
        )

        assert not result.data.delete_flow_run.success


class TestIdempotentCreateRun:
    mutation = """
        mutation($input: create_flow_run_input!) {
            create_flow_run(input: $input) {
                id
            }
        }
        """

    async def test_create_idempotent_run(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)

        # first time
        result1 = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                    idempotency_key="xyz",
                )
            ),
        )

        # second time
        result2 = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, idempotency_key="xyz")),
        )

        # ids should be the same
        assert result1.data.create_flow_run.id == result2.data.create_flow_run.id


class TestGetRunsInQueue:
    mutation = """
        mutation($input: get_runs_in_queue_input!) {
            get_runs_in_queue(input: $input) {
                flow_run_ids
            }
        }
    """

    async def test_get_runs_in_queue(
        self,
        run_query,
        tenant_id,
        flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(tenant_id=tenant_id))
        )
        assert flow_run_id in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels(
        self,
        run_query,
        tenant_id,
        flow_run_id,
        labeled_flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, labels=["foo", "bar"])),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels_and_filters_for_subset(
        self,
        run_query,
        tenant_id,
        flow_run_id,
        labeled_flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(tenant_id=tenant_id, labels=["foo", "bar", "extra"])
            ),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels_for_task_runs(
        self,
        run_query,
        tenant_id,
        flow_run_id,
        labeled_flow_run_id,
        labeled_task_run_id,
    ):
        await api.states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, labels=["foo", "bar"])),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_before_certain_time(
        self,
        run_query,
        tenant_id,
        flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    before=pendulum.now("utc").subtract(days=2).isoformat(),
                )
            ),
        )
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_multiple_runs_in_queue_before_certain_time(
        self,
        run_query,
        tenant_id,
        flow_id,
    ):
        now = pendulum.now("utc")

        # delete all other flow runs
        await models.FlowRun.where().delete()

        for i in range(10):
            await api.runs.create_flow_run(
                flow_id=flow_id, scheduled_start_time=now.add(minutes=i)
            )

        for i in range(10):
            result = await run_query(
                query=self.mutation,
                variables=dict(
                    input=dict(
                        tenant_id=tenant_id,
                        before=pendulum.now("utc").add(minutes=i).isoformat(),
                    )
                ),
            )
            assert len(result.data.get_runs_in_queue.flow_run_ids) == i + 1


class TestSetFlowRunLabels:
    mutation = """
        mutation($input: set_flow_run_labels_input!) {
            set_flow_run_labels(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_run_labels(self, run_query, flow_run_id):

        fr = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert fr.labels == []

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id, labels=["big", "boo"])),
        )

        fr = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert fr.labels == ["big", "boo"]

    async def test_set_flow_run_labels_to_empty(self, run_query, labeled_flow_run_id):

        fr = await models.FlowRun.where(id=labeled_flow_run_id).first({"labels"})
        assert fr.labels

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=labeled_flow_run_id, labels=[])),
        )

        fr = await models.FlowRun.where(id=labeled_flow_run_id).first({"labels"})
        assert fr.labels == []


class TestSetFlowRunName:
    mutation = """
        mutation($input: set_flow_run_name_input!) {
            set_flow_run_name(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_run_name(self, run_query, flow_run_id):

        fr = await models.FlowRun.where(id=flow_run_id).first({"name"})
        assert fr.name != "hello"

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id, name="hello")),
        )

        fr = await models.FlowRun.where(id=flow_run_id).first({"name"})
        assert fr.name == "hello"


class TestSetTaskRunName:
    mutation = """
        mutation($input: set_task_run_name_input!) {
            set_task_run_name(input: $input) {
                success
            }
        }
    """

    async def test_set_task_run_name(self, run_query, task_run_id):

        tr = await models.TaskRun.where(id=task_run_id).first({"name"})
        assert tr.name != "hello"

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(task_run_id=task_run_id, name="hello")),
        )

        tr = await models.TaskRun.where(id=task_run_id).first({"name"})
        assert tr.name == "hello"


class TestMappedChildren:

    query = """
        query($task_run_id: UUID!) {
            mapped_children(task_run_id: $task_run_id) {
                min_start_time
                max_end_time
                state_counts
            }
        }
        """

    @pytest.fixture(autouse=True)
    async def mapped_children(self, task_id, running_flow_run_id):
        run_ids = []
        for i in range(10):
            run_ids.append(
                await api.runs.get_or_create_task_run(
                    flow_run_id=running_flow_run_id, task_id=task_id, map_index=i
                )
            )

        # 0, 1, 2 succeed
        for i in [0, 1, 2]:
            await api.states.set_task_run_state(
                run_ids[i], prefect.engine.state.Success()
            )

        # 3, 4 fail
        for i in [3, 4]:
            await api.states.set_task_run_state(
                run_ids[i], prefect.engine.state.Failed()
            )

        # 5 retrying
        for i in [5]:
            await api.states.set_task_run_state(
                run_ids[i], prefect.engine.state.Retrying()
            )

        # 6, 7, 8 running
        for i in [6, 7, 8]:
            await api.states.set_task_run_state(
                run_ids[i], prefect.engine.state.Running()
            )

        # 9 still pending

        return run_ids

    async def test_query_mapped_children(self, task_run_id, run_query):
        result = await run_query(self.query, variables=dict(task_run_id=task_run_id))
        assert result.data.mapped_children.min_start_time is not None
        assert result.data.mapped_children.max_end_time is not None
        assert result.data.mapped_children.state_counts == {
            "Success": 3,
            "Failed": 2,
            "Retrying": 1,
            "Running": 3,
            "Pending": 1,
        }

    async def test_query_mapped_children_with_non_mapped_parent_task_run_id(
        self, task_run_id, run_query, mapped_children
    ):
        result = await run_query(
            self.query, variables=dict(task_run_id=mapped_children[1])
        )
        assert result.data.mapped_children.min_start_time is None
        assert result.data.mapped_children.max_end_time is None
        assert result.data.mapped_children.state_counts == {}

    async def test_query_mapped_children_with_invalid_task_run_id(
        self, task_run_id, run_query
    ):
        result = await run_query(
            self.query, variables=dict(task_run_id=str(uuid.uuid4()))
        )
        assert result.data.mapped_children.min_start_time is None
        assert result.data.mapped_children.max_end_time is None
        assert result.data.mapped_children.state_counts == {}
