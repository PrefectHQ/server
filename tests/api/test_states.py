import asyncio
import uuid
from typing import List

import pendulum
import pytest
from asynctest import CoroutineMock
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
    Queued,
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
from prefect.serialization.state import StateSchema

state_schema = StateSchema()


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
            if not s().is_running() and not s().is_submitted() and not s().is_queued()
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


class TestTaskRunVersionLocking:
    @pytest.fixture(autouse=True)
    async def enable_flow_run_locking(self, flow_group_id):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        flow_group.settings["version_locking_enabled"] = True
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": flow_group.settings}
        )

    async def test_set_task_run_state_with_version_succeeds_if_version_matches(
        self, task_run_id
    ):
        result = await api.states.set_task_run_state(
            task_run_id=task_run_id, state=Failed(), version=1
        )

        query = await models.TaskRun.where(id=task_run_id).first({"version", "state"})

        assert query.version == 2
        assert query.state == "Failed"

    async def test_set_task_run_state_with_version_fails_if_version_doesnt_match(
        self, task_run_id
    ):
        with pytest.raises(ValueError, match="State update failed"):
            await api.states.set_task_run_state(
                task_run_id=task_run_id, state=Failed(), version=10
            )

    async def test_version_locking_disabled_if_version_locking_flag_set_false(
        self, flow_id, flow_group_id, flow_run_id, task_run_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(
            set={"settings": {"version_locking_enabled": False}}
        )

        # pass weird version numbers to confirm version locking is disabled
        result = await api.states.set_task_run_state(
            task_run_id=task_run_id, state=Failed(), version=1000
        )

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state"}
        )

        # confirm the version still increments
        assert task_run.version == 2
        assert task_run.state == "Failed"

    async def test_version_locking_disabled_if_version_locking_flag_not_set(
        self, flow_id, flow_group_id, flow_run_id, task_run_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(set={"settings": {}})

        # pass weird version numbers to confirm version locking is disabled
        assert await api.states.set_task_run_state(
            task_run_id=task_run_id, state=Failed(), version=1000
        )

    async def test_set_task_run_state_with_right_flow_run_version_succeeds_if_passed(
        self, flow_run_id, task_run_id
    ):
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())

        await api.states.set_task_run_state(
            task_run_id=task_run_id, state=Running(), flow_run_version=3
        )

        query = await models.TaskRun.where(id=task_run_id).first({"version", "state"})

        assert query.version == 2
        assert query.state == "Running"

    async def test_set_task_run_state_with_wrong_flow_run_version_fails(
        self, flow_run_id, task_run_id
    ):
        await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())

        with pytest.raises(ValueError, match="State update failed"):
            await api.states.set_task_run_state(
                task_run_id=task_run_id, state=Running(), flow_run_version=20
            )

        query = await models.TaskRun.where(id=task_run_id).first({"version", "state"})

        assert query.version == 1
        assert query.state == "Pending"


class TestFlowRunVersionLocking:
    @pytest.fixture(autouse=True)
    async def enable_flow_run_locking(self, flow_group_id):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        flow_group.settings["version_locking_enabled"] = True
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": flow_group.settings}
        )

    async def test_set_flow_run_state_with_version_succeeds_if_version_matches(
        self, flow_run_id
    ):
        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Failed(), version=2
        )

        query = await models.FlowRun.where(id=flow_run_id).first({"version", "state"})

        assert query.version == 3
        assert query.state == "Failed"

    async def test_set_flow_run_state_with_version_fails_if_version_doesnt_match(
        self, flow_run_id
    ):
        with pytest.raises(ValueError, match="State update failed"):
            await api.states.set_flow_run_state(
                flow_run_id=flow_run_id, state=Failed(), version=10
            )

    async def test_version_locking_disabled_if_version_locking_flag_set_false(
        self, flow_id, flow_group_id, flow_run_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(
            set={"settings": {"version_locking_enabled": False}}
        )

        # pass weird version numbers to confirm version locking is disabled

        result = await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Failed(), version=1000
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "state"}
        )

        # confirm the version still increments
        assert flow_run.version == 3
        assert flow_run.state == "Failed"

    async def test_version_locking_disabled_if_version_locking_flag_not_set(
        self, flow_id, flow_group_id, flow_run_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(set={"settings": {}})

        # pass weird version numbers to confirm version locking is disabled
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=Failed(), version=1000
        )


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


class TestQueueFlowRun:
    async def test_doeesnt_transition_on_submitted_transition_with_no_slots(
        self,
        flow_id: str,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Cloud compatability test; If a flow run is attempting to transition to
        `Submitted` and the flow runs are concurrency limited, and without
        any slots remaining, the transition should fail (not get set
        to Queued).
        """

        flow_run_id, _ = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.states.set_flow_run_state(
                    labeled_flow_run_id, Submitted(state=Scheduled())
                ),
            ]
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"state"})
        state_before = flow_run.state

        await api.states.set_flow_run_state(
            flow_run_id,
            Submitted(state=Scheduled()),
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"state"})
        assert flow_run.state not in {"Running", "Submitted", "Scheduled"}
        assert flow_run.state == "Queued"

    async def test_can_transition_to_submitted_when_slots_available(
        self,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):

        new_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Submitted()
        )
        assert new_state.state == "Submitted"

    async def test_sets_state_to_queued_on_overused_concurrency_slots(
        self,
        flow_id: str,
        tenant_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests under the scenario where two flow runs end up in a `Submitted` state
        when there was only one concurrency slot that the first of the two
        to attempt to enter a `Running` state will end up getting rerouted
        into a `Queued` state.
        """

        first_run, second_run = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
            ]
        )

        # First setting should work
        await api.states.set_flow_run_state(first_run, Submitted())

        # This is effectively recreating `set_flow_run_state` without
        # all the logic protecting against exactly what we're doing
        # here.

        ## Duplicated code

        second_flow_run = await models.FlowRun.where(id=second_run).first(
            {
                "id": True,
                "serialized_state": True,
                "version": True,
            }
        )
        existing_state = state_schema.load(second_flow_run.serialized_state)
        state = Submitted(
            state=existing_state,
            message="Submitted outside of standard API to avoid safety checks.",
        )

        second_run_submitted_state = models.FlowRunState(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            flow_run_id=second_run,
            version=second_flow_run.version + 1,
            state=type(state).__name__,
            timestamp=pendulum.now("UTC"),
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )

        await second_run_submitted_state.insert()

        ## End duplicated code

        # It shouldn't matter which run we attempt to set to `Running`
        # first.

        second_run_state = await api.states.set_flow_run_state(second_run, Running())
        assert second_run_state.state == "Queued"

        first_run_state = await api.states.set_flow_run_state(first_run, Running())
        assert first_run_state.state == "Running"

    async def test_can_transition_from_submitted_to_running_without_concurrency_limits(
        self, labeled_flow_run_id: str
    ):

        submitted_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Submitted()
        )
        assert submitted_state.state == "Submitted"

        running_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Running()
        )
        assert running_state.state == "Running"

    async def test_can_transition_from_submitted_to_running_strict_slots(
        self,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests that a flow run can transition from Submitted -> Running when
        there's only 1 slot available and the flow run is already occupying
        that slot.
        """

        submitted_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Submitted()
        )
        assert submitted_state.state == "Submitted"

        running_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Running()
        )
        assert running_state.state == "Running"

    async def test_can_transition_from_submitted_to_running_loose_slots(
        self,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests that a flow run can transition from Submitted -> Running when
        there are more than 1 available slots and the flow run is occupying
        one of the slots.
        """
        await models.FlowConcurrencyLimit.where(id=flow_concurrency_limit.id).update(
            set={"limit": 5}
        )

        submitted_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Submitted()
        )
        assert submitted_state.state == "Submitted"

        running_state = await api.states.set_flow_run_state(
            labeled_flow_run_id, Running()
        )
        assert running_state.state == "Running"

    async def set_flow_group_labels(self, flow_group_id: str, labels: List[str] = None):
        if labels is None:
            # Allows setting labels of "[]"
            labels = ["foo", "bar"]
        await models.FlowGroup.where(id=flow_group_id).update(set={"labels": labels})

    async def test_ignores_unlimited_labels(self, flow_group_id: str, flow_run_id: str):
        """
        Tests to make sure that if a label exists on the flow, but does
        not have a flow concurrency limit directly associated with it,
        that it is treated as "unlimited", and will not restrict
        flow runs transitioning to `Running`.
        """
        await self.set_flow_group_labels(flow_group_id)
        state = await api.states.set_flow_run_state(flow_run_id, Running())

        assert state.state == "Running"

    async def test_ignores_request_if_already_queued(
        self,
        flow_group_id: str,
        flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        This tests that if the existing state of the flow run is already `Queued`,
        and we're supposed to enter another `Queued` state,
        we don't enter into an endless loop where we keep pushing forward the
        start time. If that were to happen, no other Agents could pick up
        the flow run, thus "locking" the run into one execution process.
        """

        first, second, _ = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                self.set_flow_group_labels(flow_group_id),
            ]
        )

        first_state = await api.states.set_flow_run_state(first, Running())
        assert first_state.state == "Running"

        before = pendulum.now("UTC")
        await asyncio.sleep(0.001)
        second_state = await api.states.set_flow_run_state(second, Running())
        assert second_state.state == "Queued"
        assert second_state.start_time > before
        assert second_state.timestamp > before

        after = pendulum.now("UTC")
        second_state = await api.states.set_flow_run_state(second, Running())
        assert second_state.state == "Queued"
        assert second_state.start_time > before
        assert second_state.timestamp > before
        # The "updated" state doesn't actually create a new state;
        # it just returns the existing queued state
        assert second_state.timestamp < after
        assert second_state.start_time < after.add(minutes=10)

    async def test_can_set_directly_to_queued(self, flow_run_id: str):
        """
        Tests that we're able to set a run directly to `Queued`,
        even though it's an edge case of how we'd use the API.
        """

        state = await api.states.set_flow_run_state(
            flow_run_id,
            Queued(state=Submitted(state=Scheduled()), start_time=pendulum.now("UTC")),
        )
        assert state.state == "Queued"

    async def test_sets_state_to_queued_on_failed_concurrency_check(
        self,
        flow_id: str,
        flow_group_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests to make sure that if the concurrency check fails, the
        run gets set to a `Queued` state instead of a `Running` state.
        """
        first, second, _ = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                self.set_flow_group_labels(flow_group_id),
            ]
        )

        first_state = await api.states.set_flow_run_state(first, Running())
        assert first_state.state == "Running"

        second_state = await api.states.set_flow_run_state(second, Running())
        assert second_state.state == "Queued"

    async def test_requires_slots_on_all_limits(
        self,
        flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
        flow_concurrency_limit_2: models.FlowConcurrencyLimit,
    ):
        """
        Tests that the requirement is _all_ concurrency limits
        pass the check, not just a subset.
        """

        first, second, *_ = await asyncio.gather(
            *[
                api.runs.create_flow_run(
                    flow_id,
                    labels=[flow_concurrency_limit.name, flow_concurrency_limit_2.name],
                ),
                api.runs.create_flow_run(
                    flow_id,
                    labels=[flow_concurrency_limit.name, flow_concurrency_limit_2.name],
                ),
                models.FlowConcurrencyLimit.where(id=flow_concurrency_limit.id).update(
                    set={"limit": 2}
                ),
            ]
        )

        first_state = await api.states.set_flow_run_state(first, Running())
        assert first_state.state == "Running"
        # Limit 1 only has 1 slot, while the second has 2 slots
        second_state = await api.states.set_flow_run_state(second, Running())
        assert second_state.state == "Queued"

    @pytest.mark.parametrize(
        "state", [Submitted(), Cancelled(), Retrying(), Pending(), Success(), Failed()]
    )
    async def test_doesnt_interfere_with_non_running_state_changes(
        self,
        flow_run_id: str,
        flow_run_id_2: str,
        flow_group_id: str,
        flow_concurrency_limit_id: str,
        flow_concurrency_limit_id_2: str,
        state: State,
    ):
        """
        Tests that changing states to any other state than `Running`
        doesn't trigger any kind of concurrency check or limiting.
        """

        await self.set_flow_group_labels(flow_group_id)

        result = await api.states.set_flow_run_state(flow_run_id, state)
        assert result.state != "Queued"

    async def test_queued_state_wraps_old_state(
        self, flow_id: str, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        first, second = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
            ]
        )

        second_flow_run = await models.FlowRun.where(id=second).first(
            {"serialized_state"}
        )

        prior_state = state_schema.load(second_flow_run.serialized_state)

        # Should succeed
        first_state = await api.states.set_flow_run_state(first, Running())
        # Without a small sleep, the test fails occassionally b/c the event
        # loop schedules the second coroutine quicker than the first executes
        await asyncio.sleep(0.001)

        second_state = await api.states.set_flow_run_state(second, Running())
        assert second_state.state == "Queued"
        after_state = state_schema.load(second_state.serialized_state)

        assert after_state.state == prior_state
