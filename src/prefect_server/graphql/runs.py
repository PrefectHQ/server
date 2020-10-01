import asyncio
from typing import Any, List

from graphql import GraphQLResolveInfo

import prefect
from prefect import api
from prefect_server.database import postgres
from prefect_server.utilities import context
from prefect_server.utilities.graphql import mutation, query

state_schema = prefect.serialization.state.StateSchema()


@query.field("mapped_children")
async def resolve_mapped_children(
    obj: Any, info: GraphQLResolveInfo, task_run_id: str
) -> dict:
    """
    Retrieve details about a task run's mapped children
    """
    query = r"""
        SELECT
            min(task_run.start_time) AS min_start_time,
            max(task_run.end_time) AS max_end_time,
            task_run.state,
            count(*) AS count
        FROM task_run
        JOIN task_run AS reference
            ON task_run.flow_run_id = reference.flow_run_id
            AND task_run.task_id = reference.task_id
        WHERE
            reference.id = $1
            AND reference.map_index < 0
            AND task_run.map_index >= 0
        GROUP BY task_run.state;
    """

    async with postgres.get_pool_connection() as connection:
        records = await connection.fetch(query, task_run_id, timeout=0.5)

    min_start_time = min(
        [r["min_start_time"] for r in records if r["min_start_time"] is not None],
        default=None,
    )
    max_end_time = max(
        [r["max_end_time"] for r in records if r["max_end_time"] is not None],
        default=None,
    )
    state_counts = {r["state"]: r["count"] for r in records}

    return {
        "min_start_time": min_start_time,
        "max_end_time": max_end_time,
        "state_counts": state_counts,
    }


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
            labels=input.get("labels"),
        )
    }

    # return the result
    return result


@mutation.field("set_flow_run_labels")
async def resolve_set_flow_run_labels(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.runs.set_flow_run_labels(
            flow_run_id=input["flow_run_id"], labels=input["labels"]
        )
    }


@mutation.field("set_flow_run_name")
async def resolve_set_flow_run_name(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.runs.set_flow_run_name(
            flow_run_id=input["flow_run_id"], name=input["name"]
        )
    }


@mutation.field("set_task_run_name")
async def resolve_set_task_run_name(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.runs.set_task_run_name(
            task_run_id=input["task_run_id"], name=input["name"]
        )
    }


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
    agent_id = cloud_context.get("headers", {}).get("x-prefect-agent-id")

    result = await api.runs.get_runs_in_queue(
        tenant_id=input["tenant_id"],
        before=input.get("before"),
        labels=labels,
        agent_id=agent_id,
    )
    return {"flow_run_ids": result}
