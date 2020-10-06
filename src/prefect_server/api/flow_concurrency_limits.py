import asyncio
from typing import Dict, List, Optional

import prefect
from prefect import models
from prefect.engine.state import Running, Submitted
from prefect.utilities.plugins import register_api

OCCUPYING_STATES = [
    state.__name__
    for state in prefect.engine.state.__dict__.values()
    if isinstance(state, type) and issubclass(state, (Running, Submitted))
]


@register_api("flow_concurrency_limits.update_flow_concurrency_limit")
async def update_flow_concurrency_limit(tenant_id: str, name: str, limit: int) -> str:
    """
    Updates or creates a flow concurrency limit.

    Args:
        - tenant_id (str): The tenant owner of the limit
        - name (str): The name of the limit
        - limit (int): The maximum number of concurrency flows allowed

    Returns:
        - str: The ID of the created or updated flow concurrency limit

    Raises:
        - ValueError: If the `limit` is invalid
        - ValueError: If the limit exists and updating it fails
    """

    if limit <= 0:
        raise ValueError(
            (
                "Flow concurrency limits require positive integers representing"
                f" the maximum number of concurrent allowed flows. Got {limit}"
            )
        )

    existing = await models.FlowConcurrencyLimit.where(
        {"name": {"_eq": name}, "tenant_id": {"_eq": tenant_id}}
    ).first({"id", "name", "limit"})

    if not existing:
        return await models.FlowConcurrencyLimit(
            name=name, limit=limit, tenant_id=tenant_id
        ).insert()

    if not existing.limit == limit:
        result = await models.FlowConcurrencyLimit.where(id=existing.id).update(
            set=dict(limit=limit)
        )
        if not bool(result.affected_rows):
            raise ValueError("Error updating existing flow concurrency limit")

    return existing.id


@register_api("flow_concurrency_limits.delete_flow_concurrency_limit")
async def delete_flow_concurrency_limit(limit_id: str) -> bool:
    """
    Deletes a flow concurrency limit.

    Args:
        - limit_id (str): The flow concurrency limit to delete.

    Returns:
        - bool: If the delete was successful

    Raises:
        - ValueError: If an ID isn't provided
    """

    if not limit_id:
        raise ValueError("Invalid flow concurrency limit ID.")

    result = await models.FlowConcurrencyLimit.where(id=limit_id).delete()
    return bool(result.affected_rows)


@register_api("flow_concurrency_limits.try_take_flow_concurrency_slots")
async def try_take_flow_concurrency_slots(
    tenant_id: str, limit_names: List[str], flow_run_id: Optional[str] = None
) -> bool:
    """
    Determines whether a `flow_run_id` either already occupies
    a concurrency slot or can occupy a concurrency slot. If
    a `flow_run_id` is not provided, the `limit_names` are searched
    in general, seeing if there are > 0 available sots.

    A concurrency slot is "already occupied" if the flow run
    is already in a Submitted State or Running State, but
    there isn't a point of trying to grab a concurrency
    slot if the flow run is already running, so the more common
    transition is from Submitted -> Running.

    Args:
        - tenant_id (str): Tenant owning the flow_run
        - limit_names (List[str]): Concurrency limits that may
            or may not exist. Nonexistant limits are treated
            as unlimited.
        - flow_run_id (Optional[str]): ID of the flow run trying to take the slot.
            If provided, checks to see whether the run has already been
                allocated a slot. If not provided, skips that check.

    Returns:
        - bool: Whether the run already occupies or can occupy a concurrency
            slot.
    """

    if not limit_names:
        # Unlabeled runs always have available slots
        return True

    if flow_run_id is not None:
        # The flow_run_id already is occupying a slot
        num_records = await models.FlowRun.where(
            {
                "id": {"_eq": flow_run_id},
                "tenant_id": {"_eq": tenant_id},
                "state": {"_in": OCCUPYING_STATES},
            }
        ).count()

        is_occupying_run_slot = num_records == 1
    else:
        is_occupying_run_slot = False

    async def check_individual_limit(
        tenant_id: str, limit_name: str, is_occupying_run_slot: bool
    ) -> bool:

        # Checking to see if the limit exists first to avoid
        # querying the much larger flow runs table
        concurrency_limit = await models.FlowConcurrencyLimit.where(
            {"name": {"_eq": limit_name}, "tenant_id": {"_eq": tenant_id}}
        ).first({"name", "limit"})

        if not concurrency_limit:
            # Not explicitly limited, considered unlimited.
            return True

        occupied_slots = await models.FlowRun.where(
            {
                "tenant_id": {"_eq": tenant_id},
                "state": {"_in": OCCUPYING_STATES},
                "labels": {"_contains": [limit_name]},
            }
        ).count()

        if is_occupying_run_slot:
            occupied_slots -= 1

        return concurrency_limit.limit > occupied_slots

    slot_occupancies = await asyncio.gather(
        *[
            check_individual_limit(
                tenant_id=tenant_id,
                limit_name=limit_name,
                is_occupying_run_slot=is_occupying_run_slot,
            )
            for limit_name in limit_names
        ]
    )

    return all(slot_occupancies)
