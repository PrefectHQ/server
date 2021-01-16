import asyncio
from typing import Tuple

import pytest

import prefect
from prefect import api, models
from prefect.engine.state import (
    Failed,
    Paused,
    Pending,
    Retrying,
    Running,
    Scheduled,
    Success,
)
from prefect.environments import LocalEnvironment
from prefect.environments.storage import Local
from prefect_server.utilities.tests import set_temporary_config

# we attach this dictionary to a module so that
# cloudpickle tracks all references to it
# see https://github.com/cloudpipe/cloudpickle/issues/275
prefect.RESULTS = {}
state_schema = prefect.serialization.state.StateSchema()


async def await_flow_run_state(
    flow_run_id, target_state_type, timeout_seconds=5
) -> Tuple[models.FlowRun, dict]:
    ready = False
    waited = 0
    task_states = {}
    while not ready and waited < timeout_seconds:
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {
                    "task": {"slug"},
                    "serialized_state": True,
                    "map_index": True,
                },
            }
        )
        if fr.serialized_state["type"] == target_state_type:
            ready = True
            task_states = {
                (tr.task.slug, tr.map_index): state_schema.load(tr.serialized_state)
                for tr in fr.task_runs
            }
        waited += 1
    return fr, task_states


def add_state_handler(flow):
    """
    Makes it so every Finished task in the flow stores its result in a prefect.RESULTS dict
    """

    def state_handler(task, old_state, new_state):
        if new_state.is_finished():
            map_index = prefect.context.get("map_index")
            if map_index is None:
                map_index = -1
            prefect.RESULTS[(task.slug, map_index)] = new_state.result
        return new_state

    for task in flow.tasks:
        task.state_handlers.append(state_handler)


class TestSimpleMap:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """

        @prefect.task
        def numbers():
            return [1, 2, 3]

        @prefect.task
        def add(x, y):
            return x + y

        with prefect.Flow(
            "simple map",
            environment=LocalEnvironment(),
            storage=Local(directory=tmpdir),
        ) as flow:
            flow.numbers1 = numbers()
            flow.numbers2 = numbers()
            flow.add = add.map(flow.numbers1, flow.numbers2)

        add_state_handler(flow)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run_succeeds(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Success")
        assert fr.serialized_state["type"] == "Success"

        # numbers1 task
        assert task_states[(flow.numbers1.slug, -1)].is_successful()
        # numbers2 task
        assert task_states[(flow.numbers2.slug, -1)].is_successful()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_mapped()
        # add children tasks
        for i in range(3):
            assert task_states[(flow.add.slug, i)].is_successful()

    @pytest.mark.xfail(
        reason="this test relied on start_tasks, which are no longer passed"
    )
    async def test_start_with_one_root_then_other_succeeds(
        self, tenant_id, flow, agent
    ):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await api.states.set_flow_run_state(flow_run_id, state=Running())

        # ----------------------------------------------------------
        # first run - start with numbers 1

        # schedule numbers1 task to run
        await api.states.set_task_run_state(
            task_run_id=await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.numbers1.id
            ),
            state=Scheduled(),
        )

        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Running", 1)

        assert fr.serialized_state["type"] == "Running"
        assert len(task_states) == 3
        # numbers1 task
        assert task_states[(flow.numbers1.slug, -1)].is_successful()
        # numbers2 task
        assert task_states[(flow.numbers2.slug, -1)].is_pending()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_pending()

        # ----------------------------------------------------------
        # second run - start with numbers 2

        # schedule numbers 2 task to run
        await api.states.set_task_run_state(
            task_run_id=await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.numbers2.id
            ),
            state=Scheduled(),
        )

        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Success")

        assert fr.serialized_state["type"] == "Success"
        assert len(task_states) == 6
        # numbers1 task
        assert task_states[(flow.numbers1.slug, -1)].is_successful()
        # numbers2 task
        assert task_states[(flow.numbers2.slug, -1)].is_successful()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_mapped()

        # add child tasks
        for i in range(3):
            assert task_states[(flow.add.slug, i)].is_successful()


class TestMapWithSkips:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """

        @prefect.task
        def numbers():
            return [1, 2, 3]

        @prefect.task
        def add(x):
            if x == 2:
                raise prefect.engine.signals.SKIP("Don't run for 2")
            return x + 10

        with prefect.Flow(
            "simple map",
            environment=LocalEnvironment(),
            storage=Local(directory=tmpdir),
        ) as flow:
            flow.numbers = numbers()
            flow.add1 = add.map(flow.numbers)
            flow.add2 = add.map(flow.add1)

        add_state_handler(flow)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Success")

        assert fr.serialized_state["type"] == "Success"
        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()

        # add1 parent task
        assert task_states[(flow.add1.slug, -1)].is_mapped()
        # add1 children tasks
        assert task_states[(flow.add1.slug, 0)].is_successful()
        assert task_states[(flow.add1.slug, 1)].is_skipped()
        assert task_states[(flow.add1.slug, 2)].is_successful()

        # add2 parent task
        assert task_states[(flow.add2.slug, -1)].is_mapped()
        # add2 children tasks
        assert task_states[(flow.add2.slug, 0)].is_successful()
        assert task_states[(flow.add2.slug, 1)].is_skipped()
        assert task_states[(flow.add2.slug, 2)].is_successful()


class TestMapWithFails:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """

        @prefect.task
        def numbers():
            return [1, 2, 3]

        @prefect.task
        def add(x):
            if x == 2:
                raise prefect.engine.signals.FAIL("Don't run for 2")
            return x + 10

        with prefect.Flow(
            "simple map",
            environment=LocalEnvironment(),
            storage=Local(directory=tmpdir),
        ) as flow:
            flow.numbers = numbers()
            flow.add1 = add.map(flow.numbers)
            flow.add2 = add.map(flow.add1)

        add_state_handler(flow)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Failed")

        assert fr.serialized_state["type"] == "Failed"

        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()

        # add1 parent task
        assert task_states[(flow.add1.slug, -1)].is_mapped()
        # add1 children tasks
        assert task_states[(flow.add1.slug, 0)].is_successful()
        assert task_states[(flow.add1.slug, 1)].is_failed()
        assert task_states[(flow.add1.slug, 2)].is_successful()

        # add2 parent task
        assert task_states[(flow.add2.slug, -1)].is_mapped()
        # add2 children tasks
        assert task_states[(flow.add2.slug, 0)].is_successful()
        assert task_states[(flow.add2.slug, 1)].is_failed()
        assert task_states[(flow.add2.slug, 2)].is_successful()
        assert prefect.RESULTS[(flow.add2.slug, 0)] == 21
        assert prefect.RESULTS[(flow.add2.slug, 2)] == 23


class TestMapWithFailsAndRunFinishedTrigger:
    @pytest.fixture()
    async def flow(self, project_id, tmpdir):
        """
        A simple diamond flow
        """

        @prefect.task
        def numbers():
            return [1, 2, 3]

        @prefect.task
        def add(x):
            if x == 2:
                raise prefect.engine.signals.FAIL("Don't run for 2")
            elif not isinstance(x, int):
                return -99
            return x + 10

        with prefect.Flow(
            "simple map",
            environment=LocalEnvironment(),
            storage=Local(directory=tmpdir),
        ) as flow:
            flow.numbers = numbers()
            flow.add1 = add.map(flow.numbers)
            flow.add2 = add.map(flow.add1)
            flow.add2.trigger = prefect.triggers.all_finished

        add_state_handler(flow)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the db
        await asyncio.sleep(1.0)

        fr, task_states = await await_flow_run_state(flow_run_id, "Success")

        assert fr.serialized_state["type"] == "Success"

        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()

        # add1 parent task
        assert task_states[(flow.add1.slug, -1)].is_mapped()
        # add1 children tasks
        assert task_states[(flow.add1.slug, 0)].is_successful()
        assert task_states[(flow.add1.slug, 1)].is_failed()
        assert task_states[(flow.add1.slug, 2)].is_successful()

        # add2 parent task
        assert task_states[(flow.add2.slug, -1)].is_mapped()
        # add2 children tasks
        assert task_states[(flow.add2.slug, 0)].is_successful()
        assert task_states[(flow.add2.slug, 1)].is_successful()
        assert task_states[(flow.add2.slug, 2)].is_successful()
        assert prefect.RESULTS[(flow.add2.slug, 0)] == 21
        assert prefect.RESULTS[(flow.add2.slug, 1)] == -99
        assert prefect.RESULTS[(flow.add2.slug, 2)] == 23
