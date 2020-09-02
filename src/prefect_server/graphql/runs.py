import asyncio
from typing import Any, List

from graphql import GraphQLResolveInfo

import prefect
from prefect import api
from prefect_server.utilities import context
from prefect_server.utilities.graphql import mutation

state_schema = prefect.serialization.state.StateSchema()


@mutation.field("create_flow_run")
async def resolve_create_flow_run(
    obj: Any, info: GraphQLResolveInfo, input: dict = None
) -> dict:

    input = input or {}

    flow_identifier = input.get("flow_id") or input.get("version_group_id")
    if not flow_identifier:
        raise ValueError("A flow id or version group ID must be provided.")

    # compute actual result
    result = {
        "id": await api.runs.create_flow_run(
            flow_id=input.get("flow_id"),
            parameters=input.get("parameters"),
            context=input.get("context"),
            scheduled_start_time=input.get("scheduled_start_time"),
            flow_run_name=input.get("flow_run_name"),
            version_group_id=input.get("version_group_id"),
            idempotency_key=input.get("idempotency_key"),
        )
    }

    # return the result
    return result


@mutation.field("get_or_create_task_run")
async def resolve_get_or_create_task_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.runs.get_or_create_task_run(
            flow_run_id=input["flow_run_id"],
            task_id=input["task_id"],
            map_index=input.get("map_index"),
        )
    }


@mutation.field("get_or_create_mapped_task_run_children")
async def resolve_get_or_create_mapped_task_run_children(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> List[dict]:
    task_runs = await api.runs.get_or_create_mapped_task_run_children(
        flow_run_id=input["flow_run_id"],
        task_id=input["task_id"],
        max_map_index=input["max_map_index"],
    )
    return {"ids": task_runs}


@mutation.field("delete_flow_run")
async def resolve_delete_flow_run(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {"success": await api.runs.delete_flow_run(flow_run_id=input["flow_run_id"])}


@mutation.field("update_flow_run_heartbeat")
async def resolve_update_flow_run_heartbeat(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    # TODO: defer db writes
    asyncio.create_task(
        api.runs.update_flow_run_heartbeat(flow_run_id=input["flow_run_id"])
    )
    return {"success": True}


@mutation.field("update_task_run_heartbeat")
async def resolve_update_task_run_heartbeat(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    # TODO: defer db writes
    asyncio.create_task(
        api.runs.update_task_run_heartbeat(task_run_id=input["task_run_id"])
    )
    return {"success": True}


@mutation.field("get_runs_in_queue")
async def resolve_get_runs_in_queue(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    labels = input.get("labels", [])
    labels.sort()

    cloud_context = context.get_context()
    agent_instance_id = cloud_context.get("headers", {}).get("x-prefect-agent-id")
    await api.agents.update_agent_instance_last_queried(
        agent_instance_id=agent_instance_id
    )

    result = await api.runs.get_runs_in_queue(
        tenant_id=input["tenant_id"],
        before=input.get("before"),
        labels=labels,
    )
    return {"flow_run_ids": result}
