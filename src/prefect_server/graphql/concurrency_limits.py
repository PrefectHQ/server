from prefect import api
from graphql import GraphQLResolveInfo
from prefect_server.utilities.graphql import mutation
from typing import Any


@mutation.field("update_flow_concurrency_limit")
async def resolve_update_flow_concurrency_limit(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:

    return {
        "id": await api.concurrency_limits.update_flow_concurrency_limit(
            tenant_id=input["tenant_id"], name=input["name"], limit=input["limit"]
        )
    }


@mutation.field("delete_flow_concurrency_limit")
async def resolve_delete_flow_concurrency_limit(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:

    was_deleted = await api.concurrency_limits.delete_flow_concurrency_limit(
        input["limit_id"]
    )
    if not was_deleted:
        raise ValueError("Could not delete flow concurrency limit")

    return {"success": True}
