import asyncio
import datetime

import pytest

import prefect
from prefect import api, models
from prefect.engine.state import Pending, Retrying, Running, Success
from prefect_server.utilities.tests import set_temporary_config

state_schema = prefect.serialization.state.StateSchema()


class TestDiamond:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """
        flow = prefect.Flow(
            "diamond",
            storage=prefect.environments.storage.Local(directory=tmpdir),
            environment=prefect.environments.LocalEnvironment(),
        )

        flow.a = prefect.Task("a")
        flow.b = prefect.Task("b")
        flow.c = prefect.Task("c")
        flow.d = prefect.Task("d")

        flow.add_edge(flow.a, flow.b)
        flow.add_edge(flow.a, flow.c)
        flow.add_edge(flow.b, flow.d)
        flow.add_edge(flow.c, flow.d)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run_succeeds(self, flow, agent):
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

        assert fr.serialized_state["type"] == "Success"
        assert task_states == {t.slug: Success() for t in flow.tasks}

    async def test_single_run_doesnt_run_if_state_set_finished(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await api.states.set_flow_run_state(flow_run_id, state=Success())
        run = await models.FlowRun.where(id=flow_run_id).first(
            {"heartbeat"}, apply_schema=True
        )
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "heartbeat": True,
                "serialized_state": True,
                "task_runs": {"serialized_state"},
            },
        )
        assert fr.heartbeat == run.heartbeat
        assert fr.serialized_state["type"] == "Success"
        assert len(fr.task_runs) == 4

    @pytest.mark.xfail(
        reason="This test relied on start_tasks, which are no longer passed."
    )
    async def test_start_two_runs_from_b_and_c(self, flow, agent):
        """
        https://github.com/PrefectHQ/cloud/issues/173

        This test simultates a scenario in which A is successful, B wants to be retried immediately
        and C wants to be retried after a delay. We make sure that when B starts, D doesn't run
        (because C is not finished); and when C starts later, D DOES Run because it loads B's state.
        """
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)

        # set the flow run to running
        await api.states.set_flow_run_state(flow_run_id, state=Running())
        # set A to Success
        await api.states.set_task_run_state(
            task_run_id=await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.a.id
            ),
            state=Success(),
        )
        # set B to Retrying
        await api.states.set_task_run_state(
            await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.b.id
            ),
            state=Retrying(),
        )

        # -------------------------------------------
        # this run should only run B and attempt D
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

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
        assert isinstance(task_states[flow.a.slug], Success)
        assert isinstance(task_states[flow.b.slug], Success)
        assert isinstance(task_states[flow.c.slug], Pending)
        assert isinstance(task_states[flow.d.slug], Pending)

        # -------------------------------------------
        # this run should run C and D

        # set C to Retrying
        await api.states.set_task_run_state(
            await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.c.id
            ),
            state=Retrying(),
        )

        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

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
        assert isinstance(task_states[flow.a.slug], Success)
        assert isinstance(task_states[flow.b.slug], Success)
        assert isinstance(task_states[flow.c.slug], Success)
        assert isinstance(task_states[flow.d.slug], Success)


class TestDiamondFailOnce:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A diamond flow whose tasks always fail the first time
        """

        class FailOnceTask(prefect.Task):
            def __init__(self, name):
                super().__init__(
                    name=name, retry_delay=datetime.timedelta(seconds=0), max_retries=1
                )

            def run(self):
                if prefect.context.task_run_count <= 1:
                    raise ValueError("Run me again!")

        flow = prefect.Flow(
            "diamond fail once",
            storage=prefect.environments.storage.Local(directory=tmpdir),
            environment=prefect.environments.LocalEnvironment(),
        )

        flow.a = FailOnceTask("a")
        flow.b = FailOnceTask("b")
        flow.c = FailOnceTask("c")
        flow.d = FailOnceTask("d")

        flow.add_edge(flow.a, flow.b)
        flow.add_edge(flow.a, flow.c)
        flow.add_edge(flow.b, flow.d)
        flow.add_edge(flow.c, flow.d)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_run_should_succeed_all_tasks(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        # this used to be called four times but now that retries happen in process, only one
        # is needed
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

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
        assert isinstance(task_states[flow.a.slug], Success)
        assert isinstance(task_states[flow.b.slug], Success)
        assert isinstance(task_states[flow.c.slug], Success)
        assert isinstance(task_states[flow.d.slug], Success)

        retries = await models.TaskRunState.where(
            {
                "task_run": {"flow_run_id": {"_eq": flow_run_id}},
                "state": {"_eq": "Retrying"},
            }
        ).count()

        # there should have been 4 retries
        assert retries == 4
