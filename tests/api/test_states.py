import uuid

import pendulum
import pytest
from box import Box

from prefect import api, models
from prefect.engine.result import SafeResult
from prefect.engine.result_handlers import JSONResultHandler
from prefect.engine.state import (
    Cancelled,
    Failed,
    Finished,
    Looped,
    Mapped,
    Paused,
    Pending,
    Retrying,
    Running,
    Scheduled,
    State,
    Submitted,
    Success,
    TimedOut,
    TriggerFailed,
    _MetaState,
)


class TestTaskRunStates:
    async def test_set_task_run_state(self, task_run_id):
        result = await api.states.set_task_run_state(
            task_run_id=task_run_id, state=Failed()
        )

        assert result.task_run_id == task_run_id

        query = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 2
        assert query.state == "Failed"
        assert query.serialized_state["type"] == "Failed"

    @pytest.mark.parametrize("state", [Failed(), Success()])
    async def test_set_task_run_state_fails_with_wrong_task_run_id(self, state):
        with pytest.raises(ValueError, match="State update failed"):
            await api.states.set_task_run_state(
                task_run_id=str(uuid.uuid4()), state=state
            )

    @pytest.mark.parametrize(
        "state", [s() for s in State.children() if not s().is_running()]
    )
    async def test_state_does_not_set_heartbeat_unless_running(
        self, state, task_run_id
    ):
        task_run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert task_run.heartbeat is None

        await api.states.set_task_run_state(task_run_id=task_run_id, state=state)

        task_run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert task_run.heartbeat is None

    async def test_running_state_sets_heartbeat(self, task_run_id, running_flow_run_id):
        task_run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert task_run.heartbeat is None

        dt = pendulum.now("UTC")
        await api.states.set_task_run_state(task_run_id=task_run_id, state=Running())

        task_run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert task_run.heartbeat > dt

    async def test_trigger_failed_state_does_not_set_end_time(self, task_run_id):
        await api.states.set_task_run_state(
            task_run_id=task_run_id, state=TriggerFailed()
        )
        task_run_info = await models.TaskRun.where(id=task_run_id).first(
            {"id", "start_time", "end_time"}
        )
        assert not task_run_info.start_time
        assert not task_run_info.end_time

    @pytest.mark.parametrize(
        "state",
        [s() for s in State.children() if s not in _MetaState.children()],
        ids=[s.__name__ for s in State.children() if s not in _MetaState.children()],
    )
    async def test_setting_a_task_run_state_pulls_cached_inputs_if_possible(
        self, task_run_id, state, running_flow_run_id
    ):

        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Failed(cached_inputs=complex_result)
        await models.TaskRun.where(id=task_run_id).update(
            set=dict(serialized_state=cached_state.serialize())
        )

        # try to schedule the task run to scheduled
        await api.states.set_task_run_state(task_run_id=task_run_id, state=state)

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"serialized_state"}
        )

        # ensure the state change took place
        assert task_run.serialized_state["type"] == type(state).__name__
        assert task_run.serialized_state["cached_inputs"]["x"]["value"] == 1
        assert task_run.serialized_state["cached_inputs"]["y"]["value"] == {"z": 2}

    @pytest.mark.parametrize(
        "state",
        [
            s(cached_inputs=None)
            for s in State.children()
            if s not in _MetaState.children()
        ],
        ids=[s.__name__ for s in State.children() if s not in _MetaState.children()],
    )
    async def test_task_runs_with_null_cached_inputs_do_not_overwrite_cache(
        self, state, task_run_id, running_flow_run_id
    ):

        await api.states.set_task_run_state(task_run_id=task_run_id, state=state)
        # set up a Retrying state with non-null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Retrying(cached_inputs=complex_result)
        await api.states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        run = await models.TaskRun.where(id=task_run_id).first({"serialized_state"})

        assert run.serialized_state["cached_inputs"]["x"]["value"] == 1
        assert run.serialized_state["cached_inputs"]["y"]["value"] == {"z": 2}

    @pytest.mark.parametrize(
        "state_cls", [s for s in State.children() if s not in _MetaState.children()]
    )
    async def test_task_runs_cached_inputs_give_preference_to_new_cached_inputs(
        self, state_cls, task_run_id, running_flow_run_id
    ):

        # set up a Failed state with null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"a": 2}, result_handler=JSONResultHandler())
        complex_result = {"b": res1, "c": res2}
        cached_state = state_cls(cached_inputs=complex_result)
        await api.states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        # set up a Retrying state with non-null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Retrying(cached_inputs=complex_result)
        await api.states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        run = Box(
            await models.TaskRun.where(id=task_run_id).first({"serialized_state"})
        )

        # verify that we have cached inputs, and that preference has been given to the new
        # cached inputs
        assert run.serialized_state.cached_inputs
        assert run.serialized_state.cached_inputs.x.value == 1
        assert run.serialized_state.cached_inputs.y.value == {"z": 2}

    @pytest.mark.parametrize(
        "flow_run_state", [Pending(), Running(), Failed(), Success()]
    )
    async def test_running_states_can_not_be_set_if_flow_run_is_not_running(
        self, flow_run_id, task_run_id, flow_run_state
    ):

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=flow_run_state
        )

        set_running_coroutine = api.states.set_task_run_state(
            task_run_id=task_run_id, state=Running()
        )

        if flow_run_state.is_running():
            assert await set_running_coroutine
            assert (
                await models.TaskRun.where(id=task_run_id).first({"state"})
            ).state == "Running"
        else:

            with pytest.raises(ValueError, match="is not in a running state"):
                await set_running_coroutine
            assert (
                await models.TaskRun.where(id=task_run_id).first({"state"})
            ).state != "Running"


class TestFlowRunStates:
    async def test_set_flow_run_state(self, flow_run_id):
        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Running()
        )

        assert result.flow_run_id == flow_run_id

        query = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 3
        assert query.state == "Running"
        assert query.serialized_state["type"] == "Running"

    @pytest.mark.parametrize("state", [Running(), Success()])
    async def test_set_flow_run_state_fails_with_wrong_flow_run_id(self, state):
        with pytest.raises(ValueError, match="State update failed"):
            await api.states.set_flow_run_state(
                flow_run_id=str(uuid.uuid4()), state=state
            )

    async def test_trigger_failed_state_does_not_set_end_time(self, flow_run_id):
        # there is no logic in Prefect that would create this sequence of
        # events, but a user could manually do this
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=TriggerFailed()
        )
        flow_run_info = await models.FlowRun.where(id=flow_run_id).first(
            {"id", "start_time", "end_time"}
        )
        assert not flow_run_info.start_time
        assert not flow_run_info.end_time

    @pytest.mark.parametrize(
        "state",
        [
            s()
            for s in State.children()
            if not s().is_running() and not s().is_submitted()
        ],
    )
    async def test_state_does_not_set_heartbeat_unless_running_or_submitted(
        self, state, flow_run_id
    ):
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert flow_run.heartbeat is None

        dt = pendulum.now("UTC")
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=state)

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert flow_run.heartbeat is None

    @pytest.mark.parametrize("state", [Running(), Submitted()])
    async def test_running_and_submitted_state_sets_heartbeat(self, state, flow_run_id):
        """
        Both Running and Submitted states need to set heartbeats for services like Lazarus to
        function properly.
        """
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert flow_run.heartbeat is None

        dt = pendulum.now("UTC")
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=state)

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert flow_run.heartbeat > dt

    async def test_setting_flow_run_to_cancelled_state_sets_unfinished_task_runs_to_cancelled(
        self, flow_run_id
    ):
        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"id"})
        task_run_ids = [run.id for run in task_runs]
        # update the state to Running
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
        # Currently this flow_run_id fixture has at least 3 tasks, if this
        # changes the test will need to be updated
        assert len(task_run_ids) >= 3, "flow_run_id fixture has changed"
        # Set one task run to pending, one to running, and the rest to success
        pending_task_run = task_run_ids[0]
        running_task_run = task_run_ids[1]
        rest = task_run_ids[2:]
        await api.states.set_task_run_state(
            task_run_id=pending_task_run, state=Pending()
        )
        await api.states.set_task_run_state(
            task_run_id=running_task_run, state=Running()
        )
        for task_run_id in rest:
            await api.states.set_task_run_state(
                task_run_id=task_run_id, state=Success()
            )
        # set the flow run to a cancelled state
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Cancelled())
        # Confirm the unfinished task runs have been marked as cancelled
        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"id", "state"})
        new_states = {run.id: run.state for run in task_runs}
        assert new_states[pending_task_run] == "Cancelled"
        assert new_states[running_task_run] == "Cancelled"
        assert all(new_states[id] == "Success" for id in rest)


class TestCancelFlowRun:
    @pytest.mark.parametrize("flow_run_id", [str(uuid.uuid4()), "", None])
    async def test_cancelling_bad_flow_run_id_errors(self, flow_run_id):
        with pytest.raises(ValueError, match="Invalid flow run ID"):
            await api.states.cancel_flow_run(flow_run_id=flow_run_id)

    async def test_cancelling_finished_flow_run_is_noop(self, flow_run_id):
        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Success()
        )
        assert result.flow_run_id == flow_run_id
        assert result.state == "Success"

        result = await api.states.cancel_flow_run(flow_run_id=flow_run_id)
        assert result.id == flow_run_id
        assert result.state == "Success"

    async def test_cancelling_running_flow_run_returns_cancelling(self, flow_run_id):
        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Running()
        )
        assert result.flow_run_id == flow_run_id
        assert result.state == "Running"

        result = await api.states.cancel_flow_run(flow_run_id=flow_run_id)
        assert result.flow_run_id == flow_run_id
        assert result.state == "Cancelling"

    async def test_cancelling_non_running_flow_run_returns_cancelled(self, flow_run_id):
        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Submitted()
        )
        assert result.flow_run_id == flow_run_id
        assert result.state == "Submitted"

        result = await api.states.cancel_flow_run(flow_run_id=flow_run_id)
        assert result.flow_run_id == flow_run_id
        assert result.state == "Cancelled"
