import datetime
import uuid

import pendulum
import pydantic
import pytest

import prefect
from prefect.utilities.graphql import EnumValue
from prefect import api
from prefect_server.database import models


@pytest.fixture
def flow():
    flow = prefect.Flow(name="my flow")
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", cache_key="test-key", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))
    mapped_task = prefect.Task("t3", tags={"mapped"})
    flow.add_edge(prefect.Parameter("y"), mapped_task, key="y", mapped=True)
    flow.add_edge(prefect.Task("t4"), mapped_task, key="not_mapped")
    return flow


class TestFlowModels:
    async def test_delete_flow_group_cascades_to_flow(self, flow_id, flow_group_id):
        # confirm the flow belongs to the flow group
        flow = await models.Flow.where(id=flow_id).first({"flow_group_id"})
        assert flow.flow_group_id == flow_group_id
        # delete the flow group
        await models.FlowGroup.where(id=flow_group_id).delete()
        # confirm the flow is no longer there
        flow = await models.Flow.where(id=flow_id).first()
        assert flow is None

    async def test_delete_flow_does_not_cascade_to_flow_group(
        self, flow_id, flow_group_id
    ):
        # delete the flow
        await models.Flow.where(id=flow_id).delete()
        # confirm the flow group isn't none
        flow_group = await models.FlowGroup.where(id=flow_group_id).first()
        assert flow_group is not None


class TestCreateFlow:
    async def test_create_flow(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        assert await models.Flow.exists(flow_id)

    async def test_create_old_and_valid_flow(self, project_id, flow):
        serialized_flow = flow.serialize()
        serialized_flow["environment"]["__version__"] = "0.0.42"
        with pytest.raises(ValueError, match="requires new flows to be built with"):
            await api.flows.create_flow(
                project_id=project_id, serialized_flow=serialized_flow
            )

    async def test_create_invalid_flow_raises_error(self, project_id, flow):
        serialized_flow = flow.serialize()
        for idx, task in enumerate(serialized_flow["tasks"]):
            if task["name"] == "t4":
                serialized_flow["tasks"][idx]["retry_delay"] = "hello there"
        with pytest.raises(pydantic.ValidationError) as exc:
            await api.flows.create_flow(
                project_id=project_id, serialized_flow=serialized_flow
            )
        assert "retry_delay" in str(exc)

    async def test_create_flow_with_extra_fields_is_ok(self, project_id, flow):
        # simulate new fields that might be added by users / Core in addition to those
        # described by the schema
        serialized_flow = flow.serialize()
        serialized_flow["an_extra_field"] = 1
        serialized_flow["an_extra_parent_field"] = {"child_field": 2}
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=serialized_flow
        )
        model = await models.Flow.where(id=flow_id).first({"serialized_flow"})
        assert model.serialized_flow["an_extra_field"] == 1
        assert model.serialized_flow["an_extra_parent_field"]["child_field"] == 2

    async def test_create_flow_is_not_archived(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_create_empty_flow(self, project_id):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=prefect.Flow(name="test").serialize()
        )
        assert await models.Flow.exists(flow_id)

    async def test_create_flow_without_edges(self, project_id):
        flow = prefect.Flow(name="test")
        flow.add_task(prefect.Task())
        flow.add_task(prefect.Task())

        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=prefect.Flow(name="test").serialize()
        )
        assert await models.Flow.exists(flow_id)

    async def test_create_flow_also_creates_tasks(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Flow.where(id=flow_id).first(
            {"tasks_aggregate": {"aggregate": {"count"}}}, apply_schema=False
        )
        assert result.tasks_aggregate.aggregate.count == len(flow.tasks)

    async def test_create_flow_saves_task_triggers(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Flow.where(id=flow_id).first({"tasks": {"trigger"}})
        assert "prefect.triggers.all_successful" in {t.trigger for t in result.tasks}

    async def test_create_flow_saves_custom_task_triggers(self, project_id, flow):

        task = list(flow.tasks)[0]
        task.trigger = api.flows.create_flow

        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Flow.where(id=flow_id).first({"tasks": {"trigger"}})
        assert "prefect_server._api.flows.create_flow" in {
            t.trigger for t in result.tasks
        }

    async def test_create_flow_also_creates_tasks_with_cache_keys(
        self, project_id, flow
    ):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Flow.where(id=flow_id).first({"tasks": {"cache_key"}})
        assert "test-key" in {t.cache_key for t in result.tasks}

    async def test_create_flow_tracks_mapped_tasks(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Flow.where(id=flow_id).first({"tasks": {"mapped"}})
        assert True in {t.mapped for t in result.tasks}

    async def test_create_flow_tracks_root_tasks(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_root_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"t1", "t4", "x", "y"}

    async def test_create_flow_tracks_terminal_tasks(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_terminal_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"x", "t2", "t3"}

    async def test_create_flow_tracks_reference_tasks(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_reference_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"x", "t2", "t3"}

    async def test_create_flow_tracks_updated_reference_tasks(self, project_id, flow):
        t3 = flow.get_tasks(name="t3")[0]
        t4 = flow.get_tasks(name="t4")[0]
        flow.set_reference_tasks([t3, t4])

        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        result = await models.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_reference_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"t3", "t4"}

    async def test_flows_can_be_safely_created_twice(self, project_id, flow):
        """
        Because object ids are not the same as database ids, the same flow can be uploaded twice
        """
        flow_id_1 = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        flow_id_2 = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        assert flow_id_1 != flow_id_2

        assert (
            await models.Flow.where({"id": {"_in": [flow_id_1, flow_id_2]}}).count()
            == 2
        )
        assert (
            await models.Task.where(
                {"flow_id": {"_in": [flow_id_1, flow_id_2]}}
            ).count()
            == len(flow.tasks) * 2
        )

    async def test_create_flow_with_schedule(self, project_id):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        flow = await models.Flow.where(id=flow_id).first({"schedule"})

        flow.schedule = prefect.serialization.schedule.ScheduleSchema().load(
            flow.schedule
        )

        assert len(flow.schedule.clocks) == 1
        assert isinstance(flow.schedule.clocks[0], prefect.schedules.clocks.CronClock)

    async def test_create_flow_with_schedule_is_active(self, project_id):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})

        assert flow.is_schedule_active

    async def test_create_flow_with_inactive_schedule(self, project_id):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=flow.serialize(),
            set_schedule_active=False,
        )

        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})

        assert not flow.is_schedule_active

    async def test_create_flow_with_fake_project(self, project_id):
        with pytest.raises(ValueError) as exc:
            await api.flows.create_flow(
                project_id=str(uuid.uuid4()),
                serialized_flow=prefect.Flow(name="test").serialize(),
            )
        assert "Invalid project" in str(exc.value)

    async def test_parameter_handling(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        f = await models.Flow.where(id=flow_id).first({"parameters"})

        f.parameters = prefect.serialization.task.ParameterSchema().load(
            f.parameters, many=True
        )
        assert isinstance(f.parameters, list)
        assert all([isinstance(p, prefect.Parameter) for p in f.parameters])
        assert len(f.parameters) == len(flow.parameters())
        assert {p.name for p in f.parameters} == {"x", "y"}
        assert {p.default for p in f.parameters} == {None, 1}
        assert {p.required for p in f.parameters} == {True, False}

    async def test_create_flow_intelligently_handles_scheduled_param_defaults(
        self, project_id
    ):
        a, b = prefect.Parameter("a"), prefect.Parameter("b", default=1)
        clock = prefect.schedules.clocks.CronClock(
            cron=f"* * * * *", parameter_defaults={"a": 1, "b": 2}
        )
        schedule = prefect.schedules.Schedule(clocks=[clock])

        flow = prefect.Flow("test-params", tasks=[a, b], schedule=schedule)

        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        assert flow_id

    async def test_create_flow_assigns_description(
        self, project_id, flow,
    ):
        description = "test"
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=flow.serialize(),
            description=description,
        )
        flow = await models.Flow.where(id=flow_id).first("description")
        assert flow.description == description

    async def test_create_flow_persists_serialized_flow(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        persisted_flow = await models.Flow.where(id=flow_id).first({"serialized_flow"})
        # confirm the keys in the serialized flow match the form we'd expect
        assert persisted_flow.serialized_flow == flow.serialize()


class TestCreateFlowVersions:
    async def test_create_flow_assigns_random_version_group_id(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        flow_model = await models.Flow.where(id=flow_id).first(
            {"version_group_id", "version"}
        )
        assert flow_model.version_group_id
        assert flow_model.version == 1

    async def test_create_flow_creates_flow_group(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})

        # get the flow group from the DB
        flow_group = await models.FlowGroup.where(
            {"name": {"_eq": flow.version_group_id}}
        ).first({"name"})

        assert flow_group.name == flow.version_group_id

    async def test_create_flow_creates_flow_group_if_version_group_provided(
        self, project_id, flow
    ):
        version_group_id = "testing"
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=flow.serialize(),
            version_group_id=version_group_id,
        )
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})

        flow_group = await models.FlowGroup.where(
            {"name": {"_eq": flow.version_group_id}}
        ).first({"name"})
        assert flow_group.name == version_group_id

    async def test_create_flow_cannot_duplicate_flow_groups(self, project_id, flow):
        version_group_id = "testing"
        # create a flow with the same version group id/flow group name twice
        await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=flow.serialize(),
            version_group_id=version_group_id,
        )
        flow_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=flow.serialize(),
            version_group_id=version_group_id,
        )
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})
        flow_groups = await models.FlowGroup.where(
            {"name": {"_eq": flow.version_group_id}}
        ).get({"name"})
        assert len(flow_groups) == 1

    async def test_version_auto_increments_for_same_version_group(self, project_id):
        flow_1_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=prefect.Flow(name="test").serialize()
        )
        flow_1 = await models.Flow.where(id=flow_1_id).first(
            {"version_group_id", "version"}
        )

        flow2_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id=flow_1.version_group_id,
        )

        flow_2 = await models.Flow.where(id=flow2_id).first(
            {"version_group_id", "version"}
        )
        assert flow_1.version_group_id == flow_2.version_group_id
        assert flow_1.version == 1
        assert flow_2.version == 2

    async def test_custom_version_group_id(self, project_id):
        flow_1_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(name="test").serialize(),
            version_group_id="hello",
        )

        flow2_id = await api.flows.create_flow(
            project_id=project_id,
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id="hello",
        )

        flow_1 = await models.Flow.where(id=flow_1_id).first(
            {"version_group_id", "version"}
        )
        flow_2 = await models.Flow.where(id=flow2_id).first(
            {"version_group_id", "version"}
        )
        assert flow_1.version_group_id == flow_2.version_group_id == "hello"
        assert flow_1.version == 1
        assert flow_2.version == 2

    async def test_different_tenants_can_create_flow_group_of_the_same_name(
        self, flow, tenant_id
    ):
        tenant_id_2 = await api.tenants.create_tenant(name="tenant-2")
        project_1 = await api.projects.create_project(
            name="tenant 1 project", tenant_id=tenant_id
        )
        project_2 = await api.projects.create_project(
            name="tenant 2 project", tenant_id=tenant_id_2
        )
        version_group_id = "testing"

        tenant_1_flow = await api.flows.create_flow(
            project_id=project_1,
            serialized_flow=flow.serialize(),
            version_group_id=version_group_id,
        )
        tenant_2_flow = await api.flows.create_flow(
            project_id=project_2,
            serialized_flow=flow.serialize(),
            version_group_id=version_group_id,
        )
        flow_groups = await models.FlowGroup.where(
            {"name": {"_eq": version_group_id}}
        ).get({"name", "tenant_id"})
        assert len(flow_groups) == 2
        flow_group_tenant_ids = [flow_group.tenant_id for flow_group in flow_groups]
        assert tenant_id in flow_group_tenant_ids
        assert tenant_id_2 in flow_group_tenant_ids

    async def test_version_auto_increments_for_same_version_group_across_project(
        self, project_id, tenant_id
    ):
        project_2_id = await api.projects.create_project(
            tenant_id=tenant_id, name="project-2"
        )
        flow_1_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=prefect.Flow(name="test").serialize()
        )
        flow_1 = await models.Flow.where(id=flow_1_id).first(
            {"version_group_id", "version"}
        )

        flow_2_id = await api.flows.create_flow(
            project_id=project_2_id,
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id=flow_1.version_group_id,
        )

        flow_2 = await models.Flow.where(id=flow_2_id).first(
            {"version_group_id", "version"}
        )
        assert flow_1.version_group_id == flow_2.version_group_id
        assert flow_1.version == 1
        assert flow_2.version == 2

    async def test_custom_version_group_id_is_respected_only_with_tenant(
        self, project_id, tenant_id
    ):
        tenant_id_2 = await api.tenants.create_tenant(name="tenant-2")

        project1 = await api.projects.create_project(tenant_id, "test")
        project2 = await api.projects.create_project(tenant_id_2, "test 2")

        flow_1_id = await api.flows.create_flow(
            project_id=project1,
            serialized_flow=prefect.Flow(name="test").serialize(),
            version_group_id="hello",
        )

        flow2_id = await api.flows.create_flow(
            project_id=project2,
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id="hello",
        )

        flow_1 = await models.Flow.where(id=flow_1_id).first(
            {"version_group_id", "version"}
        )
        flow_2 = await models.Flow.where(id=flow2_id).first(
            {"version_group_id", "version"}
        )
        assert flow_1.version_group_id == flow_2.version_group_id == "hello"
        assert flow_1.version == 1

        # flow 2 should not have been incremented because it's in a different tenant
        assert flow_2.version == 1

    async def test_create_flow_with_tags(self, project_id, flow):
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )

        db_tasks = await models.Task.where({"flow_id": {"_eq": flow_id}}).get(
            {"name", "tags"}
        )

        for task in db_tasks:
            if task.name == "t1":
                assert isinstance(task.tags, list)
                assert set(task.tags) == {"red", "blue"}
            elif task.name == "t2":
                assert set(task.tags) == {"red", "green"}
            elif task.name == "t3":
                assert task.tags == ["mapped"]
            else:
                assert task.tags == []


class TestArchive:
    async def test_archive_flow(self, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await api.flows.archive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_flow_twice(self, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await api.flows.archive_flow(flow_id)
        await api.flows.archive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_flow_deletes_scheduled_runs(self, flow_id):
        # create scheduled api.runs since the fixture doesn't

        await api.flows.schedule_flow_runs(flow_id=flow_id)

        scheduled_runs = await models.FlowRun.where(
            {"flow_id": {"_eq": flow_id}, "state": {"_eq": "Scheduled"}}
        ).get({"id"})
        assert scheduled_runs

        await api.flows.archive_flow(flow_id)

        assert (
            await models.FlowRun.where(
                {"id": {"_in": [r.id for r in scheduled_runs]}}
            ).count()
            == 0
        )

    async def test_archive_flow_with_bad_id(self, flow_id):
        assert not await api.flows.archive_flow(str(uuid.uuid4()))

    async def test_archive_flow_with_none_id(self, flow_id):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await api.flows.archive_flow(flow_id=None)


class TestUnarchiveFlow:
    async def test_unarchive_flow(self, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await api.flows.archive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived
        await api.flows.unarchive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_unarchive_flow_twice(self, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await api.flows.archive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived
        await api.flows.unarchive_flow(flow_id)
        await api.flows.unarchive_flow(flow_id)
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_unarchive_flow_with_bad_id(self, flow_id):
        assert not await api.flows.unarchive_flow(str(uuid.uuid4()))

    async def test_unarchive_flow_with_none_id(self, flow_id):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await api.flows.unarchive_flow(flow_id=None)

    async def test_unarchive_schedules_new_runs(self, flow_id):
        await api.flows.archive_flow(flow_id=flow_id)
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.unarchive_flow(flow_id=flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10


class TestDeleteFlow:
    async def test_delete_tenant_deletes_flow(self, tenant_id, flow_id):
        await models.Tenant.where(id=tenant_id).delete()
        assert not await models.Flow.exists(flow_id)

    async def test_delete_flow_does_not_delete_tenant(self, tenant_id, flow_id):
        assert await api.flows.delete_flow(flow_id)
        assert await models.Tenant.exists(tenant_id)

    async def test_delete_flow_deletes_flow_runs(self, flow_id, flow_run_id):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Scheduled(),
        )

        assert await models.FlowRun.exists(flow_run_id)

        assert await api.flows.delete_flow(flow_id)

        assert not await models.FlowRun.exists(flow_run_id)

    async def test_delete_flow_with_none_id(self):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await api.flows.delete_flow(flow_id=None)


class TestUpdateFlowProject:
    async def test_update_flow_project(self, flow_id, tenant_id):
        # create the destination flow
        project_2 = await api.projects.create_project(
            tenant_id=tenant_id, name="Project 2"
        )
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        # confirm the flow's project isn't the newly-created one
        assert flow.project_id != project_2
        await api.flows.update_flow_project(flow_id=flow_id, project_id=project_2)
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_2

    async def test_update_flow_project_fails_with_bad_project_id(
        self, flow_id, project_id
    ):
        with pytest.raises(ValueError, match="Invalid flow or project ID"):
            await api.flows.update_flow_project(
                flow_id=flow_id, project_id=str(uuid.uuid4())
            )
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id

    async def test_update_flow_project_fails_if_project_id_none(
        self, flow_id, project_id
    ):
        with pytest.raises(ValueError, match="Invalid project ID"):
            await api.flows.update_flow_project(flow_id=flow_id, project_id=None)
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id

    async def test_update_flow_project_fails_with_bad_flow_id(
        self, flow_id, project_id
    ):
        with pytest.raises(ValueError, match="Invalid flow or project ID"):
            await api.flows.update_flow_project(
                flow_id=str(uuid.uuid4()), project_id=project_id
            )
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id

    async def test_update_flow_project_fails_if_flow_id_none(self, flow_id, project_id):
        with pytest.raises(ValueError, match="Invalid flow ID."):
            await api.flows.update_flow_project(flow_id=None, project_id=project_id)
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id


class TestUpdateFlowHeartbeat:
    async def test_disable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flows.disable_heartbeat_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is False
        assert flow_group.settings["disable_heartbeat"] is True

    async def test_enable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flows.enable_heartbeat_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is True
        assert flow_group.settings["disable_heartbeat"] is False

    async def test_disable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_heartbeat_for_flow(flow_id=None)

    async def test_enable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_heartbeat_for_flow(flow_id=None)


class TestUpdateLazarusForFlow:
    async def test_disable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", False) is True
        assert await api.flows.disable_lazarus_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": False}

    async def test_enable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": False}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", True) is False
        assert await api.flows.enable_lazarus_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": True}

    async def test_disable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_lazarus_for_flow(flow_id=None)

    async def test_enable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_lazarus_for_flow(flow_id=None)


class TestUpdateVersionLockingForFlow:
    async def test_disable_version_locking_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"version_locking_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("version_locking_enabled", False) is True
        assert await api.flows.disable_version_locking_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"version_locking_enabled": False}

    async def test_enable_version_locking_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"version_locking_enabled": False}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("version_locking_enabled", True) is False
        assert await api.flows.enable_version_locking_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"version_locking_enabled": True}

    async def test_disable_version_locking_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_version_locking_for_flow(flow_id=None)

    async def test_enable_version_locking_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_version_locking_for_flow(flow_id=None)


class TestSetScheduleActive:
    async def test_set_schedule_active(self, flow_id):
        await models.Flow.where(id=flow_id).update(set={"is_schedule_active": False})
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is False

        await api.flows.set_schedule_active(flow_id=flow_id)
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is True

    async def test_set_schedule_active_with_no_id(self):
        with pytest.raises(ValueError, match="Invalid flow id"):
            await api.flows.set_schedule_active(flow_id=None)

    async def test_set_schedule_active_with_bad_id(self):
        assert not await api.flows.set_schedule_active(flow_id=str(uuid.uuid4()))

    async def test_set_schedule_active_twice(self, flow_id):
        await models.Flow.where(id=flow_id).update(set={"is_schedule_active": False})
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is False

        await api.flows.set_schedule_active(flow_id=flow_id)
        await api.flows.set_schedule_active(flow_id=flow_id)
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is True

    async def test_set_schedule_active_schedules_new_runs(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

    async def test_set_schedule_active_doesnt_duplicate_runs(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)
        await api.flows.set_schedule_active(flow_id=flow_id)

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10


class TestSetScheduleInactive:
    async def test_set_schedule_inactive(self, flow_id):
        await models.Flow.where(id=flow_id).update(set={"is_schedule_active": True})
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is True

        await api.flows.set_schedule_inactive(flow_id=flow_id)
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is False

    async def test_set_schedule_inactive_with_no_id(self):
        with pytest.raises(ValueError, match="Invalid flow id"):
            await api.flows.set_schedule_inactive(flow_id=None)

    async def test_set_schedule_inactive_with_bad_id(self):
        assert not await api.flows.set_schedule_inactive(flow_id=str(uuid.uuid4()))

    async def test_set_schedule_inactive_twice(self, flow_id):
        await models.Flow.where(id=flow_id).update(set={"is_schedule_active": True})
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is True

        await api.flows.set_schedule_inactive(flow_id=flow_id)
        await api.flows.set_schedule_inactive(flow_id=flow_id)
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active is False

    async def test_set_schedule_inactive_deletes_runs(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10
        # create one manual run that won't be deleted
        await api.runs.create_flow_run(flow_id=flow_id)

        # take one auto scheduled run out of a scheduled state
        run = await models.FlowRun.where(
            {"flow_id": {"_eq": flow_id}, "auto_scheduled": {"_eq": True}}
        ).first({"id"})
        await api.states.set_flow_run_state(
            run.id, state=prefect.engine.state.Running()
        )

        await api.flows.set_schedule_inactive(flow_id=flow_id)

        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 2

    async def test_set_schedule_inactive_deletes_runs(self, flow_id):
        """
        Since scheduled run creation is facilitated by idempotency keys, we must ensure
        that api.runs can be rescheduled if the schedule is reactivated after deleting future
        api.runs.
        """

        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)
        runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert len(runs) == 10
        start_times = {r.scheduled_start_time for r in runs}

        await api.flows.set_schedule_inactive(flow_id=flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)
        new_runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert {r.scheduled_start_time for r in new_runs} == start_times

    async def test_set_schedule_inactive_deletes_runs_in_utc(self, project_id):
        """
        Ensures that toggling schedules on and off properly creates new api.runs even if the 
        schedule was in local time
        https://github.com/PrefectHQ/cloud/issues/2295
        """
        flow = prefect.Flow(
            name="test",
            schedule=prefect.schedules.IntervalSchedule(
                start_date=pendulum.now("EST"), interval=datetime.timedelta(minutes=1)
            ),
        )

        flow_id = await api.flows.create_flow(
            serialized_flow=flow.serialize(), project_id=project_id
        )

        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)
        runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert len(runs) == 10
        start_times = {r.scheduled_start_time for r in runs}

        await api.flows.set_schedule_inactive(flow_id=flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

        await api.flows.set_schedule_active(flow_id=flow_id)
        new_runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert {r.scheduled_start_time for r in new_runs} == start_times


class TestScheduledParameters:
    async def test_schedule_creates_parametrized_flow_runs(self, project_id):
        clock1 = prefect.schedules.clocks.IntervalClock(
            start_date=pendulum.now("UTC").add(minutes=1),
            interval=datetime.timedelta(minutes=2),
            parameter_defaults=dict(x="a"),
        )
        clock2 = prefect.schedules.clocks.IntervalClock(
            start_date=pendulum.now("UTC"),
            interval=datetime.timedelta(minutes=2),
            parameter_defaults=dict(x="b"),
        )

        flow = prefect.Flow(
            name="Test Scheduled Flow",
            schedule=prefect.schedules.Schedule(clocks=[clock1, clock2]),
        )
        flow.add_task(prefect.Parameter("x", default=1))
        flow_id = await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.flows.schedule_flow_runs(flow_id)) == 10

        flow_runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            selection_set={"parameters": True, "scheduled_start_time": True},
            order_by={"scheduled_start_time": EnumValue("asc")},
        )

        assert all([fr.parameters == dict(x="a") for fr in flow_runs[::2]])
        assert all([fr.parameters == dict(x="b") for fr in flow_runs[1::2]])


class TestScheduleRuns:
    async def test_schedule_runs(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.flows.schedule_flow_runs(flow_id)) == 10

    async def test_schedule_runs_doesnt_run_for_inactive_schedule(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.flows.set_schedule_inactive(flow_id)
        assert await api.flows.schedule_flow_runs(flow_id) == []

    async def test_schedule_runs_doesnt_run_for_archived_flow(
        self, flow_id,
    ):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.flows.archive_flow(flow_id)
        assert await api.flows.schedule_flow_runs(flow_id) == []

    async def test_schedule_runs_twice_doesnt_create_new_runs(
        self, flow_id,
    ):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert len(await api.flows.schedule_flow_runs(flow_id)) == 10
        assert await api.flows.schedule_flow_runs(flow_id) == []

    async def test_schedule_runs_on_create_flow(self, project_id):
        flow = prefect.Flow(
            name="test",
            schedule=prefect.schedules.IntervalSchedule(
                start_date=pendulum.datetime(2020, 1, 1),
                interval=datetime.timedelta(days=1),
            ),
        )
        await models.FlowRun.where().delete()

        run_count = await models.FlowRun.where().count()
        await api.flows.create_flow(
            project_id=project_id, serialized_flow=flow.serialize()
        )
        assert await models.FlowRun.where().count() == run_count + 10

    async def test_schedule_max_runs(self, flow_id):
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.flows.schedule_flow_runs(flow_id, max_runs=50)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 50

    async def test_schedule_flow_runs_with_no_id(self):
        with pytest.raises(ValueError, match="Invalid flow id"):
            await api.flows.schedule_flow_runs(flow_id=None)

    async def test_schedule_flow_runs_with_bad_id(self):
        assert await api.flows.schedule_flow_runs(flow_id=str(uuid.uuid4())) == []

    async def test_schedule_runs_with_flow_group_schedule(self, flow_id, flow_group_id):
        # give the flow group an active schedule
        await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id,
            clocks=[{"type": "CronClock", "cron": "0 * * * *"}],
        )

        # ensure the flow's schedule is active
        await models.Flow.where(id=flow_id).update(set=dict(is_schedule_active=True))
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()

        await api.flows.schedule_flow_runs(flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

    async def test_schedule_runs_gives_preference_to_flow_group_schedule(
        self, flow_id, flow_group_id
    ):
        # give the flow group a schedule for once a year
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(
                schedule=dict(
                    type="Schedule", clocks=[{"type": "CronClock", "cron": "0 0 1 * *"}]
                )
            )
        )
        # give the flow a schedule for once a minute
        await models.Flow.where(id=flow_id).update(
            set=dict(
                schedule=dict(
                    type="Schedule", clocks=[{"type": "CronClock", "cron": "* * * * *"}]
                )
            )
        )
        await models.Flow.where(id=flow_id).update(set=dict(is_schedule_active=True))

        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        await api.flows.schedule_flow_runs(flow_id)
        # assert the 10 scheduled runs were scheduled months out, not for the next 10 minutes
        flow_runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            selection_set={"scheduled_start_time"},
            order_by={"scheduled_start_time": EnumValue("desc")},
        )
        assert len(flow_runs) == 10
        assert flow_runs[0].scheduled_start_time > pendulum.now("utc").add(minutes=15)
