import asyncio

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


class TestSimpleReduce:
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
            return x + 1

        @prefect.task
        def get_sum(x):
            return sum(x)

        with prefect.Flow(
            "simple reduce",
            environment=LocalEnvironment(),
            storage=Local(directory=tmpdir),
        ) as flow:
            flow.numbers = numbers()
            flow.add = add.map(flow.numbers)
            flow.sum = get_sum(flow.add)

        add_state_handler(flow)

        with set_temporary_config(key="dev", value=True):
            flow.server_id = await api.flows.create_flow(
                project_id=project_id, serialized_flow=flow.serialize(build=True)
            )

        return flow

    async def test_single_run_succeeds(self, flow, agent):
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)
        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the database
        await asyncio.sleep(1.0)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {
                    "task": {"slug"},
                    "serialized_state": True,
                    "map_index": True,
                },
            },
        )

        task_states = {
            (tr.task.slug, tr.map_index): state_schema.load(tr.serialized_state)
            for tr in fr.task_runs
        }
        assert len(task_states) == 6
        assert fr.serialized_state["type"] == "Success"
        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_mapped()
        # add children tasks
        for i in range(3):
            assert task_states[(flow.add.slug, i)].is_successful()
        # sum task
        assert task_states[(flow.sum.slug, -1)].is_successful()

        assert prefect.RESULTS[(flow.sum.slug, -1)] == 9

    @pytest.mark.xfail(
        reason="this unit test creates a situation where we try to resume but have no cached_inputs. "
        "Since we don't store all success results, there's no way for it to resume properly."
    )
    async def test_resume_from_reduce(self, flow, agent):
        """
        This test sets the "sum" task to Failed before running the flow.

        It then sets it to Scheduled and reruns from that point. This tests whether "sum"
        properly loads its upstream mapped states.
        """
        flow_run_id = await api.runs.create_flow_run(flow_id=flow.server_id)

        # ----------------------------------------------------------
        # first run - start with numbers 1

        # set sum to paused so it won't run
        await api.states.set_task_run_state(
            task_run_id=await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.sum.id
            ),
            state=Failed(),
        )

        await agent.run_scheduled(flow_id=flow.server_id)
        # wait for states to be written to the database
        await asyncio.sleep(1.0)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {
                    "task": {"slug"},
                    "serialized_state": True,
                    "map_index": True,
                },
            },
        )

        task_states = {
            (tr.task.slug, tr.map_index): state_schema.load(tr.serialized_state)
            for tr in fr.task_runs
        }

        assert fr.serialized_state["type"] == "Failed"

        assert len(task_states) == 6
        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_mapped()
        # add children tasks
        for i in range(3):
            assert task_states[(flow.add.slug, i)].is_successful()
        # sum task
        assert task_states[(flow.sum.slug, -1)].is_failed()

        # ----------------------------------------------------------
        # second run - make sum scheduled and set flow to running

        await api.states.set_task_run_state(
            task_run_id=await api.runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=flow.sum.id
            ),
            state=Scheduled(),
        )
        await api.states.set_flow_run_state(flow_run_id, state=Running())

        from prefect.utilities.debug import raise_on_exception

        with raise_on_exception():
            await agent.run_scheduled(flow_id=flow.server_id)
            # wait for states to be written to the database
            await asyncio.sleep(1.0)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {
                "serialized_state": True,
                "task_runs": {
                    "task": {"slug"},
                    "serialized_state": True,
                    "map_index": True,
                },
            },
        )

        task_states = {
            (tr.task.slug, tr.map_index): state_schema.load(tr.serialized_state)
            for tr in fr.task_runs
        }

        assert fr.serialized_state["type"] == "Success"
        # numbers task
        assert task_states[(flow.numbers.slug, -1)].is_successful()
        # add parent task
        assert task_states[(flow.add.slug, -1)].is_mapped()
        # add children tasks
        for i in range(3):
            assert task_states[(flow.add.slug, i)].is_successful()
        # sum task
        assert task_states[(flow.sum.slug, -1)].is_successful()
        assert prefect.RESULTS[(flow.sum.slug, -1)] == 9
