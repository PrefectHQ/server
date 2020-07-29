from typing import Any

from graphql import GraphQLResolveInfo

import prefect
from prefect_server import api
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities.sens_o_matic_events import register_delete


@mutation.field("create_cloud_hook")
async def resolve_create_cloud_hook(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:

    hook_id = await api.cloud_hooks.create_cloud_hook(
        tenant_id=input["tenant_id"],
        type=input["type"],
        config=input.get("config"),
        version_group_id=input.get("version_group_id"),
        states=input.get("states"),
        name=input.get("name"),
    )

    return {"id": hook_id}


@mutation.field("delete_cloud_hook")
@register_delete(table_name="cloud_hook", id_key="cloud_hook_id")
async def resolve_delete_cloud_hook(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.cloud_hooks.delete_cloud_hook(
            cloud_hook_id=input["cloud_hook_id"],
        )
    }


@mutation.field("set_cloud_hook_active")
async def resolve_set_cloud_hook_active(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.cloud_hooks.set_cloud_hook_active(
            cloud_hook_id=input["cloud_hook_id"],
        )
    }


@mutation.field("set_cloud_hook_inactive")
async def resolve_set_cloud_hook_inactive(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.cloud_hooks.set_cloud_hook_inactive(
            cloud_hook_id=input["cloud_hook_id"],
        )
    }


@mutation.field("test_cloud_hook")
async def resolve_test_cloud_hook(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:

    try:
        state_type = input.get("state_type")
        if state_type == "SCHEDULED":
            state = prefect.engine.state.Scheduled("Test scheduled state")
        elif state_type == "SUBMITTED":
            state = prefect.engine.state.Submitted("Test submitted state")
        elif state_type == "RUNNING":
            state = prefect.engine.state.Running("Test running state")
        elif state_type == "SUCCESS":
            state = prefect.engine.state.Success("Test success state")
        elif state_type == "FAILED":
            state = prefect.engine.state.Failed("Test failed state")
        else:
            state = None

        await api.cloud_hooks.test_cloud_hook(
            cloud_hook_id=input["cloud_hook_id"],
            flow_run_id=input.get("flow_run_id"),
            state=state,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
