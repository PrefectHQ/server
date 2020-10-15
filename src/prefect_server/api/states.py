# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

import asyncio
import uuid

import pendulum

import prefect
from prefect import api, models
from prefect.engine.state import Cancelled, Cancelling, Queued, State
from prefect.utilities.plugins import register_api
from prefect_server.utilities import events
from prefect_server.utilities.logging import get_logger

logger = get_logger("api")

state_schema = prefect.serialization.state.StateSchema()


@register_api("states.set_flow_run_state")
async def set_flow_run_state(
    flow_run_id: str, state: State, version: int = None, agent_id: str = None
) -> models.FlowRunState:
    """
    Updates a flow run state.

    Args:
        - flow_run_id (str): the flow run id to update
        - state (State): the new state
        - version (int): a version to enforce version-locking
        - agent_id (str): the ID of an agent instance setting the state

    Returns:
        - models.FlowRunState
    """

    if flow_run_id is None:
        raise ValueError(f"Invalid flow run ID.")

    where = {
        "id": {"_eq": flow_run_id},
        "_or": [
            # EITHER version locking is enabled and versions match
            {
                "version": {"_eq": version},
                "flow": {
                    "flow_group": {
                        "settings": {"_contains": {"version_locking_enabled": True}}
                    }
                },
            },
            # OR version locking is not enabled
            {
                "flow": {
                    "flow_group": {
                        "_not": {
                            "settings": {"_contains": {"version_locking_enabled": True}}
                        }
                    }
                }
            },
        ],
    }

    flow_run = await models.FlowRun.where(where).first(
        {
            "id": True,
            "state": True,
            "serialized_state": True,
            "state_start_time": True,
            "state_message": True,
            "state_timestamp": True,
            "state_result": True,
            "name": True,
            "version": True,
            "labels": True,
            "flow": {
                "id": True,
                "name": True,
                "flow_group_id": True,
                "version_group_id": True,
            },
            "tenant": {"id", "slug"},
        }
    )

    if not flow_run:
        raise ValueError(f"State update failed for flow run ID {flow_run_id}")

    # --------------------------------------------------------
    # apply downstream updates
    # --------------------------------------------------------

    # FOR CANCELLED STATES:
    #   - set all non-finished task run states to Cancelled
    if isinstance(state, Cancelled):
        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"id", "serialized_state"})
        to_cancel = [
            t
            for t in task_runs
            if not state_schema.load(t.serialized_state).is_finished()
        ]
        # For a run with many tasks this may be a lot of tasks - at some point
        # we might want to batch this rather than kicking off lots of asyncio
        # tasks at once.
        await asyncio.gather(
            *(api.states.set_task_run_state(t.id, state) for t in to_cancel),
            return_exceptions=True,
        )

    # --------------------------------------------------------
    # Queueing runs if using concurency limits
    # --------------------------------------------------------

    if state.is_running() or state.is_submitted():
        # Flow Concurrency Limits
        # If the run is already occupying a slot (Submitted -> Running)
        # or is attempting to occupy a slot (X -> Submitted)
        # OR if the flow_run isn't labeled / has "unlimited" labels
        can_transition = (
            await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                tenant_id=flow_run.tenant_id,
                limit_names=flow_run.labels,
                flow_run_id=flow_run_id,
            )
        )

        if not can_transition:
            if state.is_submitted():
                raise ValueError("Unable to get flow run concurrency slot. Aborting.")

            existing_state = state_schema.load(flow_run.serialized_state)
            if existing_state.is_queued():

                # If the run is currently in a Queued state and is
                # being coerced into a Queued state,
                # we don't insert a new state to avoid endlessly
                # adding 10 minutes to when the flow runners would try to
                # see if the run is available to execute

                await api.runs.update_flow_run_heartbeat(flow_run_id=flow_run_id)

                flow_run_state = models.FlowRunState(
                    flow_run_id=flow_run_id,
                    tenant_id=flow_run.tenant_id,
                    version=flow_run.version,
                    state=flow_run.state,
                    serialized_state=flow_run.serialized_state,
                    start_time=flow_run.state_start_time,
                    message=flow_run.state_message,
                    result=flow_run.state_result,
                    timestamp=flow_run.state_timestamp,
                )

                return flow_run_state
            else:
                state = Queued(
                    state=existing_state,
                    message="Queued by flow run concurrency limit",
                    start_time=pendulum.now("UTC").add(minutes=10),
                )

    # --------------------------------------------------------
    # insert the new state in the database
    # --------------------------------------------------------

    flow_run_state = models.FlowRunState(
        id=str(uuid.uuid4()),
        tenant_id=flow_run.tenant_id,
        flow_run_id=flow_run_id,
        version=(flow_run.version or 0) + 1,
        state=type(state).__name__,
        timestamp=pendulum.now("UTC"),
        message=state.message,
        result=state.result,
        start_time=getattr(state, "start_time", None),
        serialized_state=state.serialize(),
    )

    await flow_run_state.insert()

    # --------------------------------------------------------
    # apply downstream updates
    # --------------------------------------------------------

    # FOR RUNNING STATES:
    #   - update the flow run heartbeat
    if state.is_running() or state.is_submitted() or state.is_queued():
        await api.runs.update_flow_run_heartbeat(flow_run_id=flow_run_id)

    # Set agent ID on flow run when submitted by agent
    if state.is_submitted() and agent_id:
        await api.runs.update_flow_run_agent(flow_run_id=flow_run_id, agent_id=agent_id)

    # --------------------------------------------------------
    # call cloud hooks
    # --------------------------------------------------------

    event = events.FlowRunStateChange(
        flow_run=flow_run,
        state=flow_run_state,
        flow=flow_run.flow,
        tenant=flow_run.tenant,
    )

    asyncio.create_task(api.cloud_hooks.call_hooks(event))

    return flow_run_state


@register_api("states.set_task_run_state")
async def set_task_run_state(
    task_run_id: str, state: State, version: int = None, flow_run_version: int = None
) -> models.TaskRunState:
    """
    Updates a task run state.

    Args:
        - task_run_id (str): the task run id to update
        - state (State): the new state
        - version (int): a version to enforce version-locking
        - flow_run_version (int): a flow run version to enforce version-lockgin

    Returns:
        - models.TaskRunState
    """

    if task_run_id is None:
        raise ValueError(f"Invalid task run ID.")

    where = {
        "id": {"_eq": task_run_id},
        "_or": [
            {
                # EITHER version locking is enabled and the versions match
                "version": {"_eq": version},
                "flow_run": {
                    "version": {"_eq": flow_run_version},
                    "flow": {
                        "flow_group": {
                            "settings": {"_contains": {"version_locking_enabled": True}}
                        }
                    },
                },
            },
            # OR version locking is not enabled
            {
                "flow_run": {
                    "flow": {
                        "flow_group": {
                            "_not": {
                                "settings": {
                                    "_contains": {"version_locking_enabled": True}
                                }
                            }
                        }
                    }
                }
            },
        ],
    }

    task_run = await models.TaskRun.where(where).first(
        {
            "id": True,
            "tenant_id": True,
            "version": True,
            "state": True,
            "serialized_state": True,
            "flow_run": {"id": True, "state": True},
        }
    )

    if not task_run:
        raise ValueError(f"State update failed for task run ID {task_run_id}")

    # ------------------------------------------------------
    # if the state is running, ensure the flow run is also running
    # ------------------------------------------------------
    if state.is_running() and task_run.flow_run.state != "Running":
        raise ValueError(
            f"State update failed for task run ID {task_run_id}: provided "
            f"a running state but associated flow run {task_run.flow_run.id} is not "
            "in a running state."
        )

    # ------------------------------------------------------
    # if we have cached inputs on the old state, we need to carry them forward
    # ------------------------------------------------------
    if not state.cached_inputs and task_run.serialized_state.get("cached_inputs", None):
        # load up the old state's cached inputs and apply them to the new state
        serialized_state = state_schema.load(task_run.serialized_state)
        state.cached_inputs = serialized_state.cached_inputs

    # --------------------------------------------------------
    # prepare the new state for the database
    # --------------------------------------------------------

    task_run_state = models.TaskRunState(
        id=str(uuid.uuid4()),
        tenant_id=task_run.tenant_id,
        task_run_id=task_run.id,
        version=(task_run.version or 0) + 1,
        timestamp=pendulum.now("UTC"),
        message=state.message,
        result=state.result,
        start_time=getattr(state, "start_time", None),
        state=type(state).__name__,
        serialized_state=state.serialize(),
    )

    await task_run_state.insert()

    # --------------------------------------------------------
    # apply downstream updates
    # --------------------------------------------------------

    # FOR RUNNING STATES:
    #   - update the task run heartbeat
    if state.is_running():
        await api.runs.update_task_run_heartbeat(task_run_id=task_run_id)

    return task_run_state


@register_api("states.cancel_flow_run")
async def cancel_flow_run(flow_run_id: str) -> models.FlowRun:
    """
    Cancel a flow run.

    If the flow run is already finished, this is a no-op.

    Args:
        - flow_run_id (str): the flow run to cancel
    """
    if not flow_run_id:
        raise ValueError("Invalid flow run ID.")

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"id", "state", "serialized_state"}
    )
    if not flow_run:
        raise ValueError(f"Invalid flow run ID: {flow_run_id}.")

    state = state_schema.load(flow_run.serialized_state)

    if state.is_finished():
        return flow_run
    else:
        if state.is_running():
            state = Cancelling("Flow run is cancelling")
        else:
            state = Cancelled("Flow run is cancelled")
        return await set_flow_run_state(flow_run_id=flow_run_id, state=state)
