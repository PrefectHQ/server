from typing import List

import pendulum

from prefect import models
from prefect.utilities.plugins import register_api
from prefect_server.utilities import context


@register_api("agents.register_agent")
async def register_agent(
    tenant_id: str,
    labels: List[str],
    agent_config_id: str = None,
    name: str = None,
    type: str = None,
) -> str:
    """
    Register a new agent

    Args:
        - tenant_id (str): the id of a tenant
        - labels (list): a list of strings representing the agent's labels
        - agent_config_id (str): the id of an agent config to link this to
        - name (str): the name of the agent
        - type (str): the type of the agent

    Returns:
        - str: the agent id
    """
    server_context = context.get_context()
    core_version = server_context.get("headers", {}).get("x-prefect-core-version")

    if not tenant_id:
        try:
            tenant_id = await models.Tenant.where({"id": {"_eq": None}}).first().id
        except:
            raise ValueError("No tenant found.")

    # Check for existing agents with these kwargs
    agent = await models.Agent.where(
        {
            "_and": [
                {"tenant_id": {"_eq": tenant_id}},
                {"name": {"_eq": name}},
                {"type": {"_eq": type}},
                {"core_version": {"_eq": core_version}},
                {"labels": {"_eq": sorted(labels or [])}},
            ]
        }
    ).first()

    # Return existing agent ID
    if agent:
        return agent.id

    # Insert new agent
    return await models.Agent(
        tenant_id=tenant_id,
        agent_config_id=agent_config_id,
        labels=sorted(labels or []),
        name=name,
        type=type,
        core_version=core_version,
    ).insert()


@register_api("agents.update_agent_last_queried")
async def update_agent_last_queried(agent_id: str) -> bool:
    """
    Update an agent's last_queried value

    Args:
        - agent_id (str): the id of the agent to update

    Returns:
        - bool: whether the update was successful
    """
    if agent_id is None:
        raise ValueError("Must supply an agent ID to update.")
    result = await models.Agent.where(id=agent_id).update(
        set={"last_queried": pendulum.now("utc")}
    )
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.delete_agent")
async def delete_agent(agent_id: str) -> bool:
    """
    Delete an agent

    Args:
        - agent_id (str): the id of the agent to delete

    Returns:
        - bool: whether the delete was successful
    """
    if agent_id is None:
        raise ValueError("Must supply an agent ID to delete.")
    result = await models.Agent.where(id=agent_id).delete()
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.create_agent_config")
async def create_agent_config(
    tenant_id: str,
    name: str,
    settings: dict,
) -> str:
    """
    Creates an agent config, returning its id

    Args:
        - tenant_id (str): the tenant id
        - name(str): the agent config name
        - settings (dict): agent config settings

    Returns:
        - str: the agent config id
    """
    return await models.AgentConfig(
        tenant_id=tenant_id, name=name, settings=settings
    ).insert()


@register_api("agents.delete_agent_config")
async def delete_agent_config(agent_config_id: str) -> bool:
    """
    Delete an agent config

    Args:
        - agent_config_id (str): the id of the agent config to delete

    Returns:
        - bool: whether the delete was successful
    """
    if agent_config_id is None:
        raise ValueError("Must supply an agent ID to delete.")
    result = await models.AgentConfig.where(id=agent_config_id).delete()
    return bool(result.affected_rows)  # type: ignore


@register_api("agents.update_agent_config")
async def update_agent_config(
    agent_config_id: str, name: str = None, settings: dict = None
) -> str:
    """
    Update an agent config

    Args:
        - agent_config_id (str): the agent config ID
        - name (str): the agent config name
        - settings (dict): the settings to set on the agent config

    Returns:
        - bool: whether the update was successful
    """
    if not agent_config_id:
        raise ValueError("Invalid agent config ID.")

    update = {}
    if name is not None:
        update["name"] = name
    if settings is not None:
        update["settings"] = settings

    result = await models.AgentConfig.where(id=agent_config_id).update(set=update)
    return bool(result.affected_rows)  # type: ignore
