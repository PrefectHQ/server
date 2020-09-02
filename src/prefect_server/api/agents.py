from typing import List

import pendulum

from prefect_server.database import models
from prefect_server.utilities import context
from prefect.utilities.plugins import register_api


@register_api("agents.register_agent_instance")
async def register_agent_instance(
    tenant_id: str,
    labels: List[str],
    agent_id: str = None,
    name: str = None,
    type: str = None,
) -> str:
    """
    Register a new agent instance

    Args:
        - tenant_id (str): the id of a tenant
        - labels (list): a list of strings representing the agent instance's labels
        - agent_id (str): the id of an agent to link this instance to
        - name (str): the name of the agent instance
        - type (str): the type of the agent instance

    Returns:
        - str: the agent instance id
    """
    server_context = context.get_context()
    core_version = server_context.get("headers", {}).get("x-prefect-core-version")

    return await models.AgentInstance(
        tenant_id=tenant_id,
        agent_id=agent_id,
        labels=labels,
        name=name,
        type=type,
        core_version=core_version,
    ).insert()


@register_api("agents.update_agent_instance_last_queried")
async def update_agent_instance_last_queried(agent_instance_id: str) -> bool:
    """
    Update an agent instance's last_queried value

    Args:
        - agent_instance_id (str): the id of the agent instance to update

    Returns:
        - bool: whether the update was successful
    """
    if agent_instance_id is None:
        raise ValueError("Must supply an agent instance ID to update.")
    result = await models.AgentInstance.where(id=agent_instance_id).update(
        set={"last_query_time": pendulum.now("utc")}
    )
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.delete_agent_instance")
async def delete_agent_instance(agent_instance_id: str) -> bool:
    """
    Delete an agent instance

    Args:
        - agent_instance_id (str): the id of the agent instance to delete

    Returns:
        - bool: whether the delete was successful
    """
    if agent_instance_id is None:
        raise ValueError("Must supply an agent instance ID to delete.")
    result = await models.AgentInstance.where(id=agent_instance_id).delete()
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.create_agent")
async def create_agent(
    tenant_id: str,
    config: dict,
) -> str:
    """
    Creates an agent, returning its id

    Args:
        - tenant_id (str): the tenant id
        - config (dict): agent configuration

    Returns:
        - str: the agent id
    """
    return await models.Agent(tenant_id=tenant_id, config=config).insert()


@register_api("agents.delete_agent")
async def delete_agent(agent_id: str) -> bool:
    """
    Delete an agent instance

    Args:
        - agent_id (str): the id of the agent to delete

    Returns:
        - bool: whether the delete was successful
    """
    if agent_id is None:
        raise ValueError("Must supply an agent ID to delete.")
    result = await models.Agent.where(id=agent_id).delete()
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.set_agent_config")
async def set_agent_config(agent_id: str, config: dict) -> str:
    """
    Update an agent config

    Args:
        - agent_id (str): the agent ID
        - config (dict): the config to set on the agent

    Returns:
        - bool: whether the update was successful
    """
    if not agent_id:
        raise ValueError("Invalid agent ID.")

    result = await models.Agent.where(id=agent_id).update(set={"config": config})
    return bool(result.affected_rows)  # type: ignore
