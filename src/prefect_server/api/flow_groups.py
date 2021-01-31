import pendulum
from typing import List, Dict, Any, Optional

from prefect import api, models
from prefect.serialization.schedule import ClockSchema
from prefect.utilities.plugins import register_api


@register_api("flow_groups.update_setting")
async def update_setting(flow_group_id: str, key: str, value: any) -> None:
    """
    Updates a single setting for a flow group

    Args:
        - flow_group_id (str): the flow id
        - key (str): the flow setting key
        - value (str): the desired value for the given key

    Returns:
        - FlowGroup: the updated FlowGroup

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    if flow_group_id is None:
        raise ValueError("Invalid flow group ID")

    # retrieve current settings so that we only update provided keys
    flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

    if not flow_group:
        raise ValueError("Invalid flow group ID")

    flow_group.settings[key] = value  # type: ignore

    # update with new settings
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set={"settings": flow_group.settings},
    )  # type: ignore

    if not result.affected_rows:
        raise ValueError("Settings update failed")


@register_api("flow_groups.set_flow_group_default_parameters")
async def set_flow_group_default_parameters(
    flow_group_id: str, parameters: dict
) -> bool:
    """Sets default value(s) for parameter(s) on a flow group

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - parameters (dict): parameter(s) to be set for the flow group

    Returns:
        - bool: whether setting the default values was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")

    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(default_parameters=parameters)
    )
    return bool(result.affected_rows)


@register_api("flow_groups.set_flow_group_schedule")
async def set_flow_group_schedule(
    flow_group_id: str, clocks: List[dict], timezone: Optional[str] = None
) -> bool:
    """
    Sets a schedule for a flow group

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - clocks (List[dict]): a list of dictionaries defining clocks for the schedule
        - timezone (str, optional): an optional timezone to set for the schedule

    Returns:
        - bool: whether setting the schedule was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if timezone:
        if timezone not in pendulum.timezones:
            raise ValueError(f"Invalid timezone provided for schedule: {timezone}")
        start_date = {
            "dt": pendulum.now(timezone).naive().to_iso8601_string(),
            "tz": timezone,
        }
    else:
        start_date = None
    for clock in clocks:
        clock["start_date"] = start_date
        try:
            ClockSchema().load(clock)
        except:
            raise ValueError(f"Invalid clock provided for schedule: {clock}")
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(schedule=dict(type="Schedule", clocks=clocks))
    )

    deleted_runs = await models.FlowRun.where(
        {
            "flow": {"flow_group_id": {"_eq": flow_group_id}},
            "state": {"_eq": "Scheduled"},
            "auto_scheduled": {"_eq": True},
        }
    ).delete()
    return bool(result.affected_rows)


@register_api("flow_groups.delete_flow_group_schedule")
async def delete_flow_group_schedule(flow_group_id: str) -> bool:
    """
    Deletes a flow group's schedule

    Args:
        - flow_group_id (str): the ID of the flow group to update

    Returns:
        - bool: whether deleting the schedule was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(schedule=None)
    )

    deleted_runs = await models.FlowRun.where(
        {
            "flow": {"flow_group_id": {"_eq": flow_group_id}},
            "state": {"_eq": "Scheduled"},
            "auto_scheduled": {"_eq": True},
        }
    ).delete()

    return bool(result.affected_rows)


@register_api("flow_groups.set_flow_group_labels")
async def set_flow_group_labels(flow_group_id: str, labels: List[str] = None) -> bool:
    """
    Sets labels for a flow group. Providing None for labels acts as a delete,
    setting the column in the database to null.

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - labels (List[str], optional): a list of labels

    Returns:
        - bool: whether setting labels for the flow group was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if labels:
        labels = list(set(labels))  # dedupe
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(labels=labels)
    )
    return bool(result.affected_rows)


@register_api("flow_groups.set_flow_group_description")
async def set_flow_group_description(
    flow_group_id: str, description: Optional[str] = None
) -> bool:
    """
    Sets description for a flow group.

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - description (str, optional): A markdown-compatible description for this flow group.
            Providing `None` resets any previous flow group
            `description` setting.

    Returns:
        - bool: whether setting `description` for the flow group was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(description=description)
    )
    return bool(result.affected_rows)


@register_api("flow_groups.set_flow_group_run_config")
async def set_flow_group_run_config(
    flow_group_id: str, run_config: Dict[str, Any] = None
) -> bool:
    """
    Sets run_config for a flow group.

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - run_config (dict, optional): a run-config override for a flow
            group. Providing `None` defaults any previous flow group
            `run_config` setting.

    Returns:
        - bool: whether setting `run_config` for the flow group was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    if not flow_group_id:
        raise ValueError("Invalid flow group ID")
    result = await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(run_config=run_config)
    )
    return bool(result.affected_rows)


@register_api("flow_groups.enable_heartbeat")
async def enable_heartbeat_for_flow(flow_group_id: str) -> bool:
    """
    Enables heartbeats for a flow

    Args:
        - flow_group_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="disable_heartbeat", value=False
    )
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="heartbeat_enabled", value=True
    )

    return True


@register_api("flow_groups.disable_heartbeat")
async def disable_heartbeat_for_flow(flow_group_id: str) -> bool:
    """
    Disables heartbeats for a flow

    Args:
        - flow_group_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="disable_heartbeat", value=True
    )
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="heartbeat_enabled", value=False
    )
    return True


@register_api("flow_groups.enable_lazarus")
async def enable_lazarus_for_flow(flow_group_id: str) -> bool:
    """
    Enables lazarus for a flow

    Args:
        - flow_group_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="lazarus_enabled", value=True
    )
    return True


@register_api("flow_groups.disable_lazarus")
async def disable_lazarus_for_flow(flow_group_id: str) -> bool:
    """
    Disables lazarus for a flow

    Args:
        - flow_group_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow ID is not provided or invalid
    """
    await api.flow_groups.update_setting(
        flow_group_id=flow_group_id, key="lazarus_enabled", value=False
    )
    return True
