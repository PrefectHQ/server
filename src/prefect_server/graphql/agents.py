from typing import Any, List

from graphql import GraphQLResolveInfo

from prefect_server import api
from prefect_server.utilities import context
from prefect_server.utilities.graphql import mutation


@mutation.field("register_agent_instance")
async def resolve_register_agent_instance(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    agent_id = await api.agents.register_agent_instance(
        tenant_id=input.get("tenant_id"),
        labels=input.get("labels", []) or [],
        agent_id=input.get("agent_id"),
        type=input["type"],
        name=input.get("name"),
    )
    return {"id": agent_id}


@mutation.field("delete_agent_instance")
async def resolve_delete_agent_instance(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.agents.delete_agent_instance(
            agent_instance_id=input["agent_instance_id"]
        )
    }


@mutation.field("create_agent")
async def resolve_create_agent(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    return {
        "id": await api.agents.create_agent(
            tenant_id=input["tenant_id"], config=input.get("config"),
        )
    }


@mutation.field("delete_agent")
async def resolve_delete_agent(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    return {"success": await api.agents.delete_agent(agent_id=input["agent_id"])}


@mutation.field("set_agent_config")
async def resolve_set_agent_config(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    agent_id = input["agent_id"]

    return {
        "success": await api.agents.set_agent_config(
            agent_id=agent_id, config=input["config"]
        )
    }
