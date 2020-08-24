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
        tenant_id=input.get("tenant_id"),
        labels=input.get("labels", []) or [],
        agent_id=input.get("agent_id"),
        type=input["type"],
        name=input.get("name"),
    )
    return {"id": agent_id}
