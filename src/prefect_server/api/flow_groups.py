from typing import List

from prefect.serialization.schedule import ClockSchema

from prefect import api
from prefect_server.database import models
from prefect.utilities.plugins import register_api


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
async def set_flow_group_schedule(flow_group_id: str, clocks: List[dict]) -> bool:
    """
    Sets a schedule for a flow group

    Args:
        - flow_group_id (str): the ID of the flow group to update
        - clocks (List[dict]): a list of dictionaries defining clocks for the schedule

    Returns:
        - bool: whether setting the schedule was successful

    Raises:
        - ValueError: if flow group ID isn't provided
    """
    for clock in clocks:
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
