import asyncio
import json
import sys
from typing import Any

from graphql import GraphQLResolveInfo

import prefect
from prefect import api
from prefect_server.utilities.graphql import mutation

state_schema = prefect.serialization.state.StateSchema()


@mutation.field("set_flow_run_states")
async def resolve_set_flow_run_states(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Sets the flow run state, first deserializing a State from the provided input.
    """

    async def check_size_and_set_state(state_input: dict) -> str:
        state_size = sys.getsizeof(json.dumps(state_input["state"]))
        if state_size > 1000000:  # 1 mb max
            raise ValueError("State payload is too large.")

        state = state_schema.load(state_input["state"])

        flow_run_id = state_input.get("flow_run_id")
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, version=state_input.get("version"), state=state
        )

        return {"id": flow_run_id, "status": "SUCCESS", "message": None}

    result = await asyncio.gather(
        *[check_size_and_set_state(state_input) for state_input in input["states"]]
    )

    return {"states": result}


@mutation.field("set_task_run_states")
async def resolve_set_task_run_states(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Sets the task run state, first deserializing a State from the provided input.
    """

    async def check_size_and_set_state(state_input: dict) -> str:

        state_size = sys.getsizeof(json.dumps(state_input["state"]))
        if state_size > 1000000:  # 1 mb max
            raise ValueError("State payload is too large.")

        state = state_schema.load(state_input["state"])

        task_run_id = state_input.get("task_run_id")
        flow_run_version = state_input.get("flow_run_version") or state_input.get(
            "flowRunVersion"
        )
        new_task_run_state = await api.states.set_task_run_state(
            task_run_id=task_run_id,
            version=state_input.get("version"),
            state=state,
            flow_run_version=flow_run_version,
        )

        # the state was forcibily queued
        if state.is_running() and new_task_run_state.state == "Queued":
            return {
                "id": task_run_id,
                "status": "QUEUED",
                "message": new_task_run_state.serialized_state["message"],
            }
        else:
            return {"id": task_run_id, "status": "SUCCESS", "message": None}

    result = await asyncio.gather(
        *[check_size_and_set_state(state_input) for state_input in input["states"]]
    )

    return {"states": result}


@mutation.field("cancel_flow_run")
async def resolve_cancel_flow_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    """
    Cancel a flow run if the flow run isn't already Finished"
    """
    flow_run = await api.states.cancel_flow_run(input["flow_run_id"])
    return {"state": flow_run.state}
