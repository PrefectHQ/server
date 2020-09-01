from prefect import api
from prefect_server.database import models
from prefect.utilities.plugins import register_api


@register_api("flows._update_flow_setting")
async def _update_flow_setting(flow_id: str, key: str, value: any) -> models.FlowGroup:
    """
    Updates a single setting for a flow

    Args:
        - flow_id (str): the flow id
        - key (str): the flow setting key
        - value (str): the desired value for the given key

    Returns:
        - FlowGroup: the updated FlowGroup

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    if flow_id is None:
        raise ValueError("Invalid flow ID")

    # retrieve current settings so that we only update provided keys
    flow = await models.Flow.where(id=flow_id).first(
        selection_set={"version_group_id": True, "flow_group": {"id", "settings"}}
    )

    # if we don't have permission to view the flow, we shouldn't be able to update it
    if not flow:
        raise ValueError("Invalid flow ID")

    flow.flow_group.settings[key] = value  # type: ignore

    # update with new settings
    result = await models.FlowGroup.where(id=flow.flow_group.id).update(
        set={"settings": flow.flow_group.settings},
        selection_set={"returning": {"id", "settings"}, "affected_rows": True},
    )  # type: ignore

    if not result.affected_rows:
        raise ValueError("Settings update failed")

    return models.FlowGroup(**result.returning[0])


@register_api("flows.enable_heartbeat_for_flow")
async def enable_heartbeat_for_flow(flow_id: str) -> bool:
    """
    Enables heartbeats for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="disable_heartbeat", value=False
    )
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="heartbeat_enabled", value=True
    )

    return True


@register_api("flows.disable_heartbeat_for_flow")
async def disable_heartbeat_for_flow(flow_id: str) -> bool:
    """
    Disables heartbeats for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="disable_heartbeat", value=True
    )
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="heartbeat_enabled", value=False
    )
    return True


@register_api("flows.enable_lazarus_for_flow")
async def enable_lazarus_for_flow(flow_id: str) -> bool:
    """
    Enables lazarus for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="lazarus_enabled", value=True
    )
    return True


@register_api("flows.disable_lazarus_for_flow")
async def disable_lazarus_for_flow(flow_id: str) -> bool:
    """
    Disables lazarus for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="lazarus_enabled", value=False
    )
    return True


@register_api("flows.enable_version_locking_for_flow")
async def enable_version_locking_for_flow(flow_id: str) -> bool:
    """
    Enables version locking for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="version_locking_enabled", value=True
    )
    return True


@register_api("flows.disable_version_locking_for_flow")
async def disable_version_locking_for_flow(flow_id: str) -> bool:
    """
    Disables version locking for a flow

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flows._update_flow_setting(
        flow_id=flow_id, key="version_locking_enabled", value=False
    )
    return True
