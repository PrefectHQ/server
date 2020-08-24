from typing import List

import pendulum

from prefect_server.database import models
from prefect_server.utilities import context
from prefect.utilities.plugins import register_api


@register_api("agents.register_agent")
async def register_agent(
    tenant_id: str,
    labels: List[str],
    agent_id: str = None,
    name: str = None,
    type: str = None,
) -> dict:
    server_context = context.get_context()
    core_version = server_context.get("headers", {}).get("x-prefect-core-version")

    return await models.AgentRun(
        tenant_id=tenant_id,
        agent_id=agent_id,
        labels=labels,
        name=name,
        type=type,
        core_version=core_version,
    ).insert()


@register_api("agents.update_agent_last_queried")
async def update_agent_last_queried(agent_run_id: str) -> bool:
    """
    Update an agent's last_queried value

    Args:
        - agent_id (str): the id of the agent to update

    Returns:
        - bool: whether the update was successful
    """
    if agent_run_id is None:
        raise ValueError("Must supply an agent ID to update.")
    result = await models.AgentRun.where({"id": {"_eq": agent_run_id}}).update(
        set={"last_query_time": pendulum.now("utc")}
    )

    if not result.affected_rows:
        return False

    return True


# @register_api("agents.delete_agent")
# async def delete_agent(agent_id: str) -> bool:
#     """
#     Delete an agent

#     Args:
#         - agent_id (str): the id of the agent to delete

#     Returns:
#         - bool: whether the delete was successful
#     """
#     if agent_id is None:
#         raise ValueError("Must supply an agent ID to delete.")
#     return models delete
