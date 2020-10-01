import uuid

import pendulum
import pytest

import prefect
from prefect import api, models
from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Running,
    Scheduled,
    Submitted,
    Success,
)
from prefect.utilities.graphql import EnumValue, with_args
from prefect_server import config
from prefect_server.utilities.exceptions import NotFound


@pytest.fixture
async def simple_flow_id(project_id):
    return await api.flows.create_flow(
        project_id=project_id, serialized_flow=prefect.Flow(name="test").serialize()
    )


class TestCreateRun:
    async def test_create_flow_run(self, simple_flow_id):
        flow_run_id = await api.runs.create_flow_run(flow_id=simple_flow_id)
        assert await models.FlowRun.exists(flow_run_id)

    async def test_create_flow_run_accepts_labels(self, simple_flow_id):
        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, labels=["one", "two"]
        )
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert flow_run.labels == ["one", "two"]

    async def test_create_flow_run_respects_flow_group_labels(
        self,
        tenant_id,
        labeled_flow_id,
    ):
        # update the flow group's labels
        labels = ["meep", "morp"]
        labeled_flow = await models.Flow.where(id=labeled_flow_id).first(
            {"flow_group_id"}
        )
        await api.flow_groups.set_flow_group_labels(
            flow_group_id=labeled_flow.flow_group_id, labels=labels
        )
        # create a run
        flow_run_id = await api.runs.create_flow_run(flow_id=labeled_flow_id)
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert flow_run.labels == ["meep", "morp"]

    async def test_create_flow_run_respects_flow_labels(
        self,
        tenant_id,
        labeled_flow_id,
    ):
        labeled_flow = await models.Flow.where(id=labeled_flow_id).first(
            {"environment"}
        )
        # create a flow run
        flow_run_id = await api.runs.create_flow_run(flow_id=labeled_flow_id)
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert flow_run.labels == sorted(labeled_flow.environment["labels"])

    async def test_create_flow_run_respects_empty_flow_group_labels(
        self,
        tenant_id,
        labeled_flow_id,
    ):
        labeled_flow = await models.Flow.where(id=labeled_flow_id).first(
            {"flow_group_id"}
        )
        await api.flow_groups.set_flow_group_labels(
            flow_group_id=labeled_flow.flow_group_id, labels=[]
        )
        # create a run
        flow_run_id = await api.runs.create_flow_run(flow_id=labeled_flow_id)
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert flow_run.labels == []

    async def test_create_flow_run_with_version_group_id(self, project_id):
        flow_ids = []
        for _ in range(15):
            flow_ids.append(
                await api.flows.create_flow(
                    project_id=project_id,
                    serialized_flow=prefect.Flow(name="test").serialize(),
                    version_group_id="test-group",
                )
            )

        flow_id = flow_ids.pop(7)

        for fid in flow_ids:
            await api.flows.archive_flow(fid)

        flow_run_id = await api.runs.create_flow_run(version_group_id="test-group")
        fr = await models.FlowRun.where(id=flow_run_id).first({"flow": {"id": True}})

        assert fr.flow.id == flow_id

    async def test_create_flow_run_with_version_group_id_uses_latest_version(
        self, project_id
    ):
        flow_ids = []
        for _ in range(15):
            flow_ids.append(
                await api.flows.create_flow(
                    project_id=project_id,
                    serialized_flow=prefect.Flow(name="test").serialize(),
                    version_group_id="test-group",
                )
            )

        first_id = flow_ids.pop(0)
        newer_id = flow_ids.pop(9)

        for fid in flow_ids:
            await api.flows.archive_flow(fid)

        flow_run_id = await api.runs.create_flow_run(version_group_id="test-group")
        fr = await models.FlowRun.where(id=flow_run_id).first({"flow": {"id": True}})

        assert fr.flow.id == newer_id

    async def test_create_flow_run_fails_if_neither_flow_nor_version_are_provided(
        self, simple_flow_id
    ):
        await api.flows.archive_flow(simple_flow_id)
        with pytest.raises(ValueError) as exc:
            await api.runs.create_flow_run(flow_id=None)
        assert "flow_id" in str(exc.value)
        assert "version_group_id" in str(exc.value)

    async def test_create_flow_run_fails_if_flow_is_archived(self, simple_flow_id):
        await api.flows.archive_flow(simple_flow_id)
        with pytest.raises(ValueError) as exc:
            await api.runs.create_flow_run(flow_id=simple_flow_id)
        assert "archived" in str(exc.value)

    async def test_create_flow_run_fails_if_all_versions_are_archived(self, project_id):
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(name="test").serialize(),
            version_group_id="test-group",
        )
        await api.flows.archive_flow(flow_id)
        with pytest.raises(NotFound) as exc:
            await api.runs.create_flow_run(version_group_id="test-group")
        assert "no unarchived flows" in str(exc.value)

    async def test_create_flow_run_creates_name(self, simple_flow_id):
        flow_run_id_1 = await api.runs.create_flow_run(flow_id=simple_flow_id)
        flow_run_id_2 = await api.runs.create_flow_run(flow_id=simple_flow_id)
        flow_run_id_3 = await api.runs.create_flow_run(flow_id=simple_flow_id)
        flow_runs = await models.FlowRun.where(
            {"id": {"_in": [flow_run_id_1, flow_run_id_2, flow_run_id_3]}}
        ).get({"name"})

        assert isinstance(flow_runs[0].name, str)
        assert len(flow_runs[0].name) > 3
        # 3 different names
        assert len(set(fr.name for fr in flow_runs)) == 3

    async def test_create_flow_run_with_flow_run_name_creates_run_name(
        self, simple_flow_id
    ):
        flow_run_id_1 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 1"
        )
        flow_run_id_2 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 2"
        )
        flow_run_id_3 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 3"
        )
        flow_runs = await models.FlowRun.where(
            {"id": {"_in": [flow_run_id_1, flow_run_id_2, flow_run_id_3]}}
        ).get({"name"})

        assert isinstance(flow_runs[0].name, str)
        assert len(flow_runs[0].name) > 3
        # 3 different names
        assert set(fr.name for fr in flow_runs) == {
            "named flow run 1",
            "named flow run 2",
            "named flow run 3",
        }

    async def test_create_run_with_missing_parameters_raises_error(self, project_id):

        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(
                name="test", tasks=[prefect.Parameter("x")]
            ).serialize(),
        )

        with pytest.raises(ValueError) as exc:
            await api.runs.create_flow_run(flow_id=flow_id)

        assert "Required parameters were not supplied" in str(exc.value)

    async def test_create_run_with_parameters(self, flow_id):
        flow_run_id = await api.runs.create_flow_run(
            flow_id=flow_id, parameters=dict(x=1)
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"parameters"})
        assert flow_run.parameters == dict(x=1)

    async def test_create_run_uses_default_flow_group_parameters(self, project_id):
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(
                name="test", tasks=[prefect.Parameter("x", default=1)]
            ).serialize(),
        )

        flow = await models.Flow.where(id=flow_id).first({"flow_group_id"})
        await prefect.api.flow_groups.set_flow_group_default_parameters(
            flow_group_id=flow.flow_group_id, parameters=dict(x=2)
        )

        flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"parameters"})
        assert flow_run.parameters == dict(x=2)

    async def test_create_run_passes_start_time_to_flow_run_record(
        self, simple_flow_id
    ):
        dt = pendulum.datetime(2020, 1, 1)

        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"scheduled_start_time"}
        )

        assert flow_run.scheduled_start_time == dt

    async def test_create_run_defaults_auto_scheduled_to_false(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)

        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"scheduled_start_time", "auto_scheduled"}
        )

        assert flow_run.scheduled_start_time == dt
        assert not flow_run.auto_scheduled

    async def test_new_run_has_scheduled_state(self, simple_flow_id):
        dt = pendulum.now()
        flow_run_id = await api.runs.create_flow_run(flow_id=simple_flow_id)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {"state", "state_start_time", "state_message"}
        )
        assert fr.state == "Scheduled"
        assert fr.state_start_time > dt
        assert fr.state_message == "Flow run scheduled."

    async def test_new_run_has_correct_state_start_time(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)
        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )
        fr = await models.FlowRun.where(id=flow_run_id).first({"state_start_time"})
        assert fr.state_start_time == dt

    async def test_new_run_state_is_in_history(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)
        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )
        frs = await models.FlowRunState.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get(
            {"state", "start_time", "message"}, order_by={"timestamp": EnumValue("asc")}
        )
        assert len(frs) == 2
        assert frs[1].state == "Scheduled"
        assert frs[1].start_time == dt
        assert frs[1].message == "Flow run scheduled."

    async def test_create_flow_run_also_creates_task_runs(self, project_id):

        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(
                name="test", tasks=[prefect.Task(), prefect.Task(), prefect.Task()]
            ).serialize(),
        )

        flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)

        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == 3
        )

    async def test_create_flow_run_also_creates_task_runs_with_cache_keys(
        self, project_id
    ):

        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(
                name="test",
                tasks=[
                    prefect.Task(cache_key="test-key"),
                    prefect.Task(),
                    prefect.Task(cache_key="wat"),
                ],
            ).serialize(),
        )

        flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)

        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"cache_key"})

        assert set(tr.cache_key for tr in task_runs) == {"test-key", "wat", None}

    async def test_create_run_creates_context(self, simple_flow_id):
        flow_run_id = await api.runs.create_flow_run(flow_id=simple_flow_id)
        fr = await models.FlowRun.where(id=flow_run_id).first({"context"})
        assert fr.context == {}

    async def test_create_run_with_context(self, simple_flow_id):
        flow_run_id = await api.runs.create_flow_run(
            flow_id=simple_flow_id, context={"a": 1, "b": 2}
        )
        fr = await models.FlowRun.where(id=flow_run_id).first({"context"})
        assert fr.context["a"] == 1
        assert fr.context["b"] == 2


class TestCreateIdempotentRun:
    async def test_create_idempotent_flow_run_with_key(self, simple_flow_id):
        flow_run_id_1 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, idempotency_key="abc"
        )
        flow_run_id_2 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, idempotency_key="abc"
        )
        flow_run_id_3 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, idempotency_key="xyz"
        )
        assert flow_run_id_1 == flow_run_id_2
        assert flow_run_id_1 != flow_run_id_3

    async def test_idempotency_key_is_scoped_to_flow_id(
        self, simple_flow_id, project_id
    ):
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(name="test").serialize(),
        )
        flow_run_id_1 = await api.runs.create_flow_run(
            flow_id=simple_flow_id, idempotency_key="abc"
        )
        flow_run_id_2 = await api.runs.create_flow_run(
            flow_id=flow_id, idempotency_key="abc"
        )
        assert flow_run_id_1 != flow_run_id_2

    async def test_idempotency_key_is_scoped_to_version_group_id(
        self, simple_flow_id, project_id
    ):
        for _ in range(3):
            await api.flows.create_flow(
                project_id=project_id,
                serialized_flow=prefect.Flow(name="test").serialize(),
                version_group_id="test-group-1",
            )

        for _ in range(3):
            await api.flows.create_flow(
                project_id=project_id,
                serialized_flow=prefect.Flow(name="test").serialize(),
                version_group_id="test-group-2",
            )

        flow_run_id_1 = await api.runs.create_flow_run(
            version_group_id="test-group-1", idempotency_key="abc"
        )
        flow_run_id_2 = await api.runs.create_flow_run(
            version_group_id="test-group-1", idempotency_key="abc"
        )
        flow_run_id_3 = await api.runs.create_flow_run(
            version_group_id="test-group-2", idempotency_key="abc"
        )
        assert flow_run_id_1 == flow_run_id_2
        assert flow_run_id_1 != flow_run_id_3


class TestGetTaskRunInfo:
    async def test_task_run(self, flow_run_id, task_id):
        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        assert await models.TaskRun.exists(tr_id)

    async def test_task_run_populates_cache_key(self, flow_run_id, task_id):
        cache_key = "test"
        # set the stage for creation with a cache_key
        await models.TaskRun.where({"task_id": {"_eq": task_id}}).delete()
        await models.Task.where(id=task_id).update(set={"cache_key": cache_key})

        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        task_run = await models.TaskRun.where(id=tr_id).first({"cache_key"})
        assert task_run.cache_key
        assert task_run.cache_key == cache_key

    async def test_task_run_does_not_populate_cache_key_unless_specified(
        self, flow_run_id, task_id
    ):
        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        task_run = await models.TaskRun.where(id=tr_id).first({"cache_key"})
        assert task_run.cache_key is None

    async def test_task_run_starts_in_pending_state(self, flow_run_id, task_id):
        tr_id_1 = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        tr_id_2 = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=12
        )
        trs = await models.TaskRun.where({"id": {"_in": [tr_id_1, tr_id_2]}}).get(
            {"state", "serialized_state"},
        )

        assert all(tr.state == "Pending" for tr in trs)
        assert all(tr.serialized_state["type"] == "Pending" for tr in trs)

    async def test_task_run_pulls_current_state(self, flow_run_id, task_id):
        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        await api.states.set_task_run_state(tr_id, state=Success())

        tr = await models.TaskRun.where(id=tr_id).first(
            {"state", "serialized_state"},
        )
        assert tr.state == "Success"
        assert tr.serialized_state["type"] == "Success"

    async def test_task_run_with_map_index_none_stored_as_negative_one(
        self, flow_run_id, task_id
    ):
        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        run = await models.TaskRun.where(id=tr_id).first(selection_set={"map_index"})
        assert run.map_index == -1

    async def test_task_run_with_map_index(self, flow_run_id, task_id):
        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=10
        )
        assert await models.TaskRun.exists(tr_id)

    async def test_task_run_fails_with_fake_flow_run_id(self, task_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.runs.get_or_create_task_run(
                flow_run_id=str(uuid.uuid4()), task_id=task_id, map_index=None
            )

    async def test_task_run_fails_with_fake_task_id(self, flow_run_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=str(uuid.uuid4()), map_index=None
            )

    async def test_task_run_retrieves_existing_task_run(
        self, flow_run_id, task_id, task_run_id
    ):

        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        assert tr_id == task_run_id

    async def test_task_run_creates_new_task_run_for_map_index(
        self, flow_run_id, task_id
    ):
        existing_task_run_ids = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get("id")

        tr_id = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )

        # id not in previous ids
        assert tr_id not in {tr.id for tr in existing_task_run_ids}

        tr_count = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).count()
        assert tr_count == len(existing_task_run_ids) + 1

    async def test_task_run_creates_new_task_run_for_map_index_on_first_call_only(
        self, flow_run_id, task_id
    ):
        existing_task_run_ids = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get("id")

        id_1 = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        id_2 = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        assert id_1 not in {tr.id for tr in existing_task_run_ids}
        assert id_2 == id_1

    async def test_task_run_inserts_state_if_tr_doesnt_exist(
        self, flow_run_id, task_id
    ):
        task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        # call multiple times to be sure
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=2
        )

        new_task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        assert new_task_run_state_count == task_run_state_count + 2

    async def test_task_run_doesnt_insert_state_if_tr_already_exists(
        self, flow_run_id, task_id, task_run_id
    ):
        task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        # call multiple times to be sure
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        await api.runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )

        new_task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        assert new_task_run_state_count == task_run_state_count


class TestGetOrCreateMappedChildren:
    async def test_get_or_create_mapped_children_creates_children(
        self, flow_id, flow_run_id
    ):
        # get a task from the flow
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first({"id"})
        task_runs = await models.TaskRun.where({"task_id": {"_eq": task.id}}).get()

        mapped_children = await api.runs.get_or_create_mapped_task_run_children(
            flow_run_id=flow_run_id, task_id=task.id, max_map_index=10
        )
        # confirm 11 children were returned as a result (indices 0, through 10)
        assert len(mapped_children) == 11
        # confirm those 11 children are in the DB
        assert len(task_runs) + 11 == len(
            await models.TaskRun.where({"task_id": {"_eq": task.id}}).get()
        )
        # confirm that those 11 children have api.states and the map indices are ordered
        map_indices = []
        for child in mapped_children:
            task_run = await models.TaskRun.where(id=child).first(
                {
                    "map_index": True,
                    with_args(
                        "states",
                        {"order_by": {"version": EnumValue("desc")}, "limit": 1},
                    ): {"id"},
                }
            )
            map_indices.append(task_run.map_index)
            assert task_run.states[0] is not None
        assert map_indices == sorted(map_indices)

    async def test_get_or_create_mapped_children_retrieves_children(
        self, flow_id, flow_run_id
    ):
        # get a task from the flow
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first(
            {"id", "cache_key"}
        )

        # create some mapped children
        task_run_ids = []
        for i in range(11):
            task_run_ids.append(
                await models.TaskRun(
                    flow_run_id=flow_run_id,
                    task_id=task.id,
                    map_index=i,
                    cache_key=task.cache_key,
                ).insert()
            )
        # retrieve those mapped children
        mapped_children = await api.runs.get_or_create_mapped_task_run_children(
            flow_run_id=flow_run_id, task_id=task.id, max_map_index=10
        )
        # confirm we retrieved 11 mapped children (0 through 10)
        assert len(mapped_children) == 11
        # confirm those 11 children are the task api.runs we created earlier and that they're in order
        map_indices = []
        for child in mapped_children:
            task_run = await models.TaskRun.where(id=child).first({"map_index"})
            map_indices.append(task_run.map_index)
            assert child in task_run_ids
        assert map_indices == sorted(map_indices)

    async def test_get_or_create_mapped_children_does_not_retrieve_parent(
        self, flow_id, flow_run_id
    ):
        # get a task from the flow
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first(
            {"id", "cache_key"}
        )
        # create a parent and its mapped children
        for i in range(3):
            await models.TaskRun(
                flow_run_id=flow_run_id,
                task_id=task.id,
                map_index=i,
                cache_key=task.cache_key,
            ).insert()

        # retrieve those mapped children
        mapped_children = await api.runs.get_or_create_mapped_task_run_children(
            flow_run_id=flow_run_id, task_id=task.id, max_map_index=2
        )
        # confirm we retrieved 3 mapped children (0, 1, and 2)
        assert len(mapped_children) == 3
        # but not the parent
        for child in mapped_children:
            task_run = await models.TaskRun.where(id=child).first({"map_index"})
            assert task_run.map_index > -1

    async def test_get_or_create_mapped_children_handles_partial_children(
        self, flow_id, flow_run_id
    ):
        # get a task from the flow
        task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first(
            {"id", "cache_key"}
        )

        # create a few mapped children
        await models.TaskRun(
            flow_run_id=flow_run_id,
            task_id=task.id,
            map_index=3,
            cache_key=task.cache_key,
        ).insert()
        stateful_child = await models.TaskRun(
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

        # retrieve mapped children
        mapped_children = await api.runs.get_or_create_mapped_task_run_children(
            flow_run_id=flow_run_id, task_id=task.id, max_map_index=10
        )
        assert len(mapped_children) == 11
        map_indices = []
        # confirm each of the mapped children has a state and is ordered properly
        for child in mapped_children:
            task_run = await models.TaskRun.where(id=child).first(
                {
                    "map_index": True,
                    with_args(
                        "states",
                        {"order_by": {"version": EnumValue("desc")}, "limit": 1},
                    ): {"id"},
                }
            )
            map_indices.append(task_run.map_index)
            assert task_run.states[0] is not None
        assert map_indices == sorted(map_indices)

        # confirm the one child created with a state only has the one state
        child_states = await models.TaskRunState.where(
            {"task_run_id": {"_eq": stateful_child}}
        ).get()
        assert len(child_states) == 1


class TestUpdateFlowRunHeartbeat:
    async def test_update_heartbeat(self, flow_run_id):
        dt = pendulum.now()
        await api.runs.update_flow_run_heartbeat(flow_run_id=flow_run_id)

        run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert dt < run.heartbeat

    async def test_update_heartbeat_with_bad_id(self):
        with pytest.raises(ValueError) as exc:
            await api.runs.update_flow_run_heartbeat(flow_run_id=str(uuid.uuid4()))
        assert "Invalid" in str(exc.value)


class TestUpdateTaskRunHeartbeat:
    async def test_update_heartbeat(self, task_run_id):
        dt = pendulum.now()
        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert run.heartbeat is None

        dt1 = pendulum.now()
        await api.runs.update_task_run_heartbeat(task_run_id=task_run_id)

        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert dt1 < run.heartbeat

    async def test_update_heartbeat_with_bad_id(self):
        with pytest.raises(ValueError) as exc:
            await api.runs.update_task_run_heartbeat(task_run_id=str(uuid.uuid4()))
        assert "Invalid" in str(exc.value)


class TestDeleteFlowRuns:
    async def test_delete_flow_run(self, flow_run_id):
        result = await api.runs.delete_flow_run(flow_run_id=flow_run_id)
        flow_run = await models.FlowRun.where(id=flow_run_id).first()

        assert result is True
        assert flow_run is None

    async def test_delete_flow_run_fails_with_invalid_id(self):
        result = await api.runs.delete_flow_run(flow_run_id=str(uuid.uuid4()))
        assert result is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, ""],
    )
    async def test_delete_flow_run_fails_if_none(self, bad_value):
        with pytest.raises(ValueError, match="Invalid flow run ID"):
            await api.runs.delete_flow_run(flow_run_id=bad_value)


class TestGetRunsInQueue:
    async def test_get_flow_run_in_queue(self, flow_run_id, tenant_id):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id in flow_runs

    async def test_get_flow_run_in_queue_uses_labels(
        self, tenant_id, flow_run_id, labeled_flow_run_id
    ):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "bar"]
        )
        assert labeled_flow_run_id in flow_runs
        assert flow_run_id not in flow_runs

    async def test_get_flow_run_in_queue_uses_run_labels(
        self,
        tenant_id,
        flow_id,
        labeled_flow_run_id,
    ):

        flow_run_id = await api.runs.create_flow_run(
            flow_id=flow_id, labels=["dev", "staging"]
        )

        flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["dev", "staging"]
        )
        assert flow_run_id in flow_runs
        assert labeled_flow_run_id not in flow_runs

    async def test_get_flow_run_in_queue_works_if_environment_labels_are_none(
        self, tenant_id, flow_run_id, flow_id
    ):
        """
        Old environments have no labels attribute, so we ensure labels are loaded as a list
        even if the labels attribute is `None`. This test would fail if `None` were loaded
        improperly.
        """

        flow = await models.Flow.where(id=flow_id).first({"environment"})
        flow.environment["labels"] = None
        await models.Flow.where(id=flow_id).update({"environment": flow.environment})
        check_flow = await models.Flow.where(id=flow_id).first({"environment"})
        assert check_flow.environment["labels"] is None

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        await api.runs.get_runs_in_queue(tenant_id=tenant_id, labels=["foo", "bar"])

    async def test_get_flow_run_in_queue_works_if_environment_labels_are_missing(
        self, tenant_id, flow_run_id, flow_id
    ):
        """
        Old environments have no labels attribute, so we ensure labels are loaded as a list
        even if the labels attribute is missing. This test would fail if it were loaded
        improperly.
        """

        flow = await models.Flow.where(id=flow_id).first({"environment"})
        del flow.environment["labels"]
        await models.Flow.where(id=flow_id).update({"environment": flow.environment})
        check_flow = await models.Flow.where(id=flow_id).first({"environment"})
        assert "labels" not in check_flow.environment

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await api.runs.get_runs_in_queue(tenant_id=tenant_id, labels=["foo", "bar"])

    async def test_get_flow_run_in_queue_filters_labels_correctly(
        self, tenant_id, flow_run_id, labeled_flow_run_id
    ):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        super_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "bar", "chris"]
        )
        random_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["dev"]
        )
        mixed_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "staging"]
        )
        assert labeled_flow_run_id in super_flow_runs
        assert flow_run_id not in super_flow_runs

        assert labeled_flow_run_id not in random_flow_runs
        assert flow_run_id not in random_flow_runs

        assert labeled_flow_run_id not in mixed_flow_runs
        assert flow_run_id not in mixed_flow_runs

    async def test_get_flow_run_in_queue_uses_labels_on_task_runs(
        self,
        tenant_id,
        flow_run_id,
        labeled_flow_run_id,
        labeled_task_run_id,
        task_run_id,
    ):

        await api.states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await api.states.set_task_run_state(
            task_run_id=task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "bar"]
        )
        assert labeled_flow_run_id in flow_runs
        assert flow_run_id not in flow_runs

    async def test_get_flow_run_in_queue_filters_labels_on_task_runs_correctly(
        self,
        tenant_id,
        flow_run_id,
        labeled_flow_run_id,
        labeled_task_run_id,
        task_run_id,
    ):

        await api.states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await api.states.set_task_run_state(
            task_run_id=task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        super_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "bar", "chris"]
        )
        random_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["dev"]
        )
        mixed_flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, labels=["foo", "staging"]
        )
        assert labeled_flow_run_id in super_flow_runs
        assert flow_run_id not in super_flow_runs

        assert labeled_flow_run_id not in random_flow_runs
        assert flow_run_id not in random_flow_runs

        assert labeled_flow_run_id not in mixed_flow_runs
        assert flow_run_id not in mixed_flow_runs

    async def test_get_flow_run_in_queue_before_certain_time(
        self, flow_run_id, tenant_id
    ):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id in flow_runs

        flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, before=pendulum.now("utc").subtract(days=2)
        )
        assert flow_run_id not in flow_runs

    async def test_get_multiple_flow_run_in_queue_before_certain_time(
        self, tenant_id, flow_id
    ):
        now = pendulum.now("utc")

        for i in range(10):
            await api.runs.create_flow_run(
                flow_id=flow_id, scheduled_start_time=now.add(minutes=i)
            )

        flow_runs = await api.runs.get_runs_in_queue(
            tenant_id=tenant_id, before=now.add(minutes=4)
        )

        assert len(flow_runs) == 5

    async def test_get_flow_run_in_queue_matches_concurrency(self, tenant_id, flow_id):

        concurrency = config.queued_runs_returned_limit

        # create more runs than concurrency allows
        for i in range(concurrency * 2):
            await api.runs.create_flow_run(flow_id=flow_id)

        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)

        # concurrency * 2 api.runs in queue, only concurrency retrieved
        assert len(flow_runs) == concurrency

    async def test_number_queued_runs_returned_is_capped_by_config_value(
        self, tenant_id, flow_id
    ):

        # create more runs than concurrency allows
        for _ in range(2 * config.queued_runs_returned_limit):
            await api.runs.create_flow_run(flow_id=flow_id)

        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)

        # confirm there are enough items for the cap to be enforced
        assert len(flow_runs) == config.queued_runs_returned_limit

    async def test_getting_a_flow_run_from_queue_doesnt_dequeue_it(
        self, flow_run_id, tenant_id
    ):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        # retrieve api.runs multiple times
        flow_runs1 = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        flow_runs2 = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        flow_runs3 = await api.runs.get_runs_in_queue(tenant_id=tenant_id)

        for frs in [flow_runs1, flow_runs2, flow_runs3]:
            assert flow_run_id in frs

    async def test_future_flow_runs_are_not_retrieved(self, flow_run_id, tenant_id):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").add(days=1)),
        )

        assert not await api.runs.get_runs_in_queue(tenant_id=tenant_id)

    async def test_flow_run_is_dequeued_when_state_changes(
        self, flow_run_id, tenant_id
    ):

        # update the run's state to scheduled
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Scheduled())

        # assert it is in the queue
        runs_in_queue = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id in runs_in_queue

        # update the run's state to finished
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Finished())

        # assert it is not in the queue
        runs_in_queue = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id not in runs_in_queue

    async def test_task_run_is_dequeued_when_state_changes(
        self, tenant_id, running_flow_run_id, task_run_id
    ):

        # update the run's state to scheduled
        await api.states.set_task_run_state(task_run_id=task_run_id, state=Scheduled())

        # assert it is in the queue
        runs_in_queue = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert running_flow_run_id in runs_in_queue

        # update the run's state to finished
        await api.states.set_task_run_state(task_run_id=task_run_id, state=Finished())

        # assert it is not in the queue
        runs_in_queue = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert running_flow_run_id not in runs_in_queue

    async def test_get_runs_in_queue_ignores_flow_runs_with_start_time_none(
        self, tenant_id, flow_run_id
    ):
        await models.FlowRun.where({"id": {"_neq": flow_run_id}}).delete()
        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Paused())
        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id not in flow_runs

    async def test_get_runs_in_queue_ignores_task_runs_with_start_time_none(
        self, tenant_id, flow_run_id, task_run_id
    ):
        await models.FlowRun.where({"id": {"_neq": flow_run_id}}).delete()
        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        await api.states.set_task_run_state(task_run_id, prefect.engine.state.Paused())
        flow_runs = await api.runs.get_runs_in_queue(tenant_id=tenant_id)
        assert flow_run_id not in flow_runs


class TestSetFlowRunLabels:
    async def test_set_flow_run_labels(self, flow_run_id):
        fr = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert fr.labels == []

        await api.runs.set_flow_run_labels(flow_run_id=flow_run_id, labels=["a", "b"])

        fr = await models.FlowRun.where(id=flow_run_id).first({"labels"})
        assert fr.labels == ["a", "b"]

    async def test_set_flow_run_labels_must_have_value(self, flow_run_id):
        with pytest.raises(ValueError, match="Invalid labels"):
            await api.runs.set_flow_run_labels(flow_run_id=flow_run_id, labels=None)

    async def test_set_flow_run_id_invalid(self):
        assert not await api.runs.set_flow_run_labels(
            flow_run_id=str(uuid.uuid4()), labels=["a"]
        )

    async def test_set_flow_run_id_none(self):
        with pytest.raises(ValueError, match="Invalid flow run ID"):
            assert not await api.runs.set_flow_run_labels(
                flow_run_id=None, labels=["a"]
            )


class TestSetFlowRunName:
    async def test_set_flow_run_name(self, flow_run_id):
        fr = await models.FlowRun.where(id=flow_run_id).first({"name"})
        assert fr.name != "hello"

        await api.runs.set_flow_run_name(flow_run_id=flow_run_id, name="hello")

        fr = await models.FlowRun.where(id=flow_run_id).first({"name"})
        assert fr.name == "hello"

    @pytest.mark.parametrize("name", [None, ""])
    async def test_set_flow_run_name_must_have_value(self, flow_run_id, name):
        with pytest.raises(ValueError, match="Invalid name"):
            await api.runs.set_flow_run_name(flow_run_id=flow_run_id, name=name)

    async def test_set_flow_run_id_invalid(self):
        assert not await api.runs.set_flow_run_name(
            flow_run_id=str(uuid.uuid4()), name="hello"
        )

    async def test_set_flow_run_id_none(self):
        with pytest.raises(ValueError, match="Invalid flow run ID"):
            assert not await api.runs.set_flow_run_name(flow_run_id=None, name="hello")


class TestSetTaskRunName:
    async def test_set_task_run_name(self, task_run_id):
        tr = await models.TaskRun.where(id=task_run_id).first({"name"})
        assert tr.name != "hello"

        await api.runs.set_task_run_name(task_run_id=task_run_id, name="hello")

        tr = await models.TaskRun.where(id=task_run_id).first({"name"})
        assert tr.name == "hello"

    @pytest.mark.parametrize("name", [None, ""])
    async def test_set_task_run_name_must_have_value(self, task_run_id, name):
        with pytest.raises(ValueError, match="Invalid name"):
            await api.runs.set_task_run_name(task_run_id=task_run_id, name=name)

    async def test_set_task_run_id_invalid(self):
        assert not await api.runs.set_task_run_name(
            task_run_id=str(uuid.uuid4()), name="hello"
        )

    async def test_set_task_run_id_none(self):
        with pytest.raises(ValueError, match="Invalid task run ID"):
            assert not await api.runs.set_task_run_name(task_run_id=None, name="hello")
