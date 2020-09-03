from typing import Any, List

from graphql import GraphQLResolveInfo

from prefect_server import api
from prefect_server.utilities import context
from prefect_server.utilities.graphql import mutation


@mutation.field("register_agent")
async def resolve_register_agent(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    agent_id = await api.agents.register_agent(
        tenant_id=input["tenant_id"],
        labels=input["labels"],
        agent_config_id=input.get("agent_config_id"),
        type=input["type"],
        name=input.get("name"),
    )
    return {"id": agent_id}


@mutation.field("delete_agent")
async def resolve_delete_agent(obj: Any, info: GraphQLResolveInfo, input: dict) -> dict:
    return {"success": await api.agents.delete_agent(agent_id=input["agent_id"])}


@mutation.field("create_agent_config")
async def resolve_create_agent_config(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "id": await api.agents.create_agent_config(
            tenant_id=input["tenant_id"],
            agent=input.get("name"),
            config=input.get("config"),
        )
    }


@mutation.field("delete_agent_config")
async def resolve_delete_agent_config(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.agents.delete_agent_config(
            agent_config_id=input["agent_config_id"]
        )
    }


@mutation.field("set_agent_config")
async def resolve_set_agent_config(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    agent_config_id = input["agent_config_id"]

    return {
        "success": await api.agents.set_agent_config(
            agent_config_id=agent_config_id, config=input["config"]
        )
    }
