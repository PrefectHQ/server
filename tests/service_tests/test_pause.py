import asyncio

import pytest

import prefect
from prefect import api, models
from prefect.engine.state import (
    Failed,
    Paused,
    Pending,
    Resume,
    Retrying,
    Running,
    Scheduled,
    Success,
)
from prefect_server.utilities.tests import set_temporary_config

state_schema = prefect.serialization.state.StateSchema()


class TestPause:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """
        flow = prefect.Flow(
            "pause",
            storage=prefect.environments.storage.Local(directory=tmpdir),
            environment=prefect.environments.LocalEnvironment(),
        )

        flow.a = prefect.Task("a")
        flow.b = prefect.Task("b", trigger=prefect.triggers.manual_only)
        flow.c = prefect.Task("c")

        flow.add_edge(flow.a, flow.b)
        flow.add_edge(flow.b, flow.c)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run_pauses(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.5)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {"task": {"slug"}, "serialized_state": True},
            },
        )
        task_states = {
            tr.task.slug: state_schema.load(tr.serialized_state) for tr in fr.task_runs
        }

        assert fr.serialized_state["type"] == "Running"
        assert task_states[flow.a.slug].is_successful()
        assert isinstance(task_states[flow.b.slug], Paused)
        assert task_states[flow.c.slug].is_pending()

    async def test_second_run_is_still_paused(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.5)

        # second run
        await agent.run_scheduled(flow_id=flow.server_id)
        await asyncio.sleep(1.5)

        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {"task": {"slug"}, "serialized_state": True},
            },
        )
        task_states = {
            tr.task.slug: state_schema.load(tr.serialized_state) for tr in fr.task_runs
        }
        assert fr.serialized_state["type"] == "Running"
        assert task_states[flow.a.slug].is_successful()
        assert isinstance(task_states[flow.b.slug], Paused)
        assert task_states[flow.c.slug].is_pending()

    async def test_setting_resume_allows_completion(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.5)

        tr = await models.TaskRun.where(
            {
                "flow_run_id": {"_eq": flow_run_id},
                "task": {"slug": {"_eq": flow.b.slug}},
            }
        ).first({"id"})

        # put tr in a resume state
        await api.states.set_task_run_state(tr.id, Resume())

        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.5)

        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {"task": {"slug"}, "serialized_state": True},
            },
        )
        task_states = {
            tr.task.slug: state_schema.load(tr.serialized_state) for tr in fr.task_runs
        }
        assert fr.serialized_state["type"] == "Success"
        assert {tr.is_successful() for tr in task_states.values()}
