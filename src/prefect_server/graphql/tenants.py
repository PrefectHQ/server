from typing import Any

from graphql import GraphQLResolveInfo

from prefect import api
from prefect_server.utilities.graphql import mutation


@mutation.field("create_tenant")
async def resolve_create_tenant(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.tenants.create_tenant(name=input["name"], slug=input["slug"])
    }


@mutation.field("delete_tenant")
async def resolve_delete_tenant(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    if not input.get("confirm"):
        raise ValueError("Must pass `confirm=True` to proceed.")

    return {"success": await api.tenants.delete_tenant(tenant_id=input["tenant_id"])}


@mutation.field("update_tenant_name")
async def resolve_update_tenant_name(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    if await api.tenants.update_name(tenant_id=input["tenant_id"], name=input["name"]):
        return {"id": input["tenant_id"]}
    else:
        raise ValueError("Update failed.")


@mutation.field("update_tenant_slug")
async def resolve_update_tenant_slug(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    if await api.tenants.update_slug(tenant_id=input["tenant_id"], slug=input["slug"]):
        return {"id": input["tenant_id"]}
    else:
        raise ValueError("Update failed.")


@mutation.field("update_tenant_settings")
async def resolve_update_tenant_settings(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    if await api.tenants.update_settings(
        tenant_id=input["tenant_id"], settings=input.get("settings", {})
    ):
        return {"id": input["tenant_id"]}
    else:
        raise ValueError("Update failed.")
