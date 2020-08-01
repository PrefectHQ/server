from typing import Any

from graphql import GraphQLResolveInfo

from prefect import api
from prefect_server.utilities.graphql import mutation
from prefect_server.utilities.sens_o_matic_events import register_delete


@mutation.field("create_project")
async def resolve_create_project(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.projects.create_project(
            name=input["name"],
            tenant_id=input["tenant_id"],
            description=input.get("description"),
        )
    }


@mutation.field("delete_project")
@register_delete(table_name="project", id_key="project_id")
async def resolve_delete_project(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.projects.delete_project(project_id=input["project_id"])
    }


@mutation.field("set_project_name")
async def resolve_set_project_name(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    project_id = input["project_id"]
    result = await api.projects.set_project_name(
        project_id=project_id, name=input["name"]
    )

    if not result:
        raise ValueError("Update failed")

    return {"id": project_id}


@mutation.field("set_project_description")
async def resolve_set_project_description(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    project_id = input["project_id"]
    result = await api.projects.set_project_description(
        project_id=project_id, description=input["description"]
    )
    if not result:
        raise ValueError("Update failed")

    return {"id": project_id}
