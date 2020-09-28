import asyncio
from typing import Dict, List

import prefect
from prefect import models
from prefect.engine.state import Running
from prefect.utilities.plugins import register_api

RUNNING_STATES = [
    state.__name__
    for state in prefect.engine.state.__dict__.values()
    if isinstance(state, type) and issubclass(state, Running)
]


@register_api("concurrency_limits.update_flow_concurrency_limit")
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


@register_api("concurrency_limits.delete_flow_concurrency_limit")
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

    result = await models.FlowConcurrencyLimit.where(
        id=limit_id
    ).delete()
    return bool(result.affected_rows)


@register_api("concurrency_limits.get_available_flow_run_concurrency")
async def get_available_flow_run_concurrency(
    tenant_id: str, labels: List[str]
) -> Dict[str, int]:
    """
    Determines the number of open flow concurrency slots are available
    given a certain flow label.

    A `Flow` is allocated a slot of concurrency when it exists in
    the `Running` state for the Execution Environment / Flow Group, and will
    continue to occupy that slot until it transitions out of
    the `Running` state.

    Args:
        - tenant_id (str): Tenant owning the flow runs and labels
        - labels (List[str]): Flow labels to get their concurrency availability.

    Returns:
        - Dict[str, int]: Number of available concurrency slots for each
            label that's passed in. If a concurrency limit is not found,
            the label won't be present in the output dictionary.
    """

    concurrency_limits = await models.FlowConcurrencyLimit.where(
        {"name": {"_in": labels}, "tenant_id": {"_eq": tenant_id}}
    ).get({"name", "limit"})
    if not concurrency_limits:
        return {}

    limits = {limit.name: limit.limit for limit in concurrency_limits}

    # These queries are done individually because Hasura doesn't
    # handle {"labels": [name, name, name]} in a way that's
    # easily able to be sent as one query. There are tests
    # verifying how Hasura handles these nested arrays in JSONB fields
    # due to how it doesn't behave how you'd expect at first glance.

    # Splitting the queries for labels that are on _either_ an environment
    # or a flow group & those with matching labels on both to avoid
    # double counting flow runs

    async def get_overlapping_label_slots(tenant_id: str, limit: str) -> Dict[str, int]:
        # Overlapping label slots meaning a flow has the same label
        # on the environment & the flow group.
        utilized_slots = {
            limit: await models.FlowRun.where(
                where={
                    "tenant_id": {"_eq": tenant_id},
                    "state": {"_in": RUNNING_STATES},
                    "flow": {
                        "environment": {"_contains": {"labels": [limit]}},
                        "flow_group": {"labels": {"_contains": [limit]}},
                    },
                }
            ).count()
        }
        return utilized_slots

    async def get_unique_label_slots(tenant_id: str, limit: str) -> Dict[str, int]:
        # Unique label slots meaning where a label is _either_
        # on a flow group or an environment, but *not* both.

        utilized_slots = {
            limit: await models.FlowRun.where(
                {
                    "tenant_id": {"_eq": tenant_id},
                    "state": {"_in": RUNNING_STATES},
                    "_or": [
                        {"flow": {"environment": {"_contains": {"labels": [limit]}}}},
                        {"flow": {"flow_group": {"labels": {"_contains": [limit]}}}},
                    ],
                    "_not": {
                        "flow": {
                            "environment": {"_contains": {"labels": [limit]}},
                            "flow_group": {"labels": {"_contains": [limit]}},
                        },
                    },
                }
            ).count()
        }

        return utilized_slots

    # 2 different functions (one execution per label) so we can await them
    # independently sending all queries at once instead of potentially
    # executing each batch ~synchronously

    futures = [
        get_overlapping_label_slots(tenant_id=tenant_id, limit=limit)
        for limit in limits.keys()
    ] + [
        get_unique_label_slots(tenant_id=tenant_id, limit=limit)
        for limit in limits.keys()
    ]

    used_flow_slots = await asyncio.gather(*futures)

    # Combining all the single key, value pairs into one holding
    # the total number of flow runs used
    used_slots: Dict[str, int] = {}
    for used_flow_slot in used_flow_slots:
        limit = list(used_flow_slot.keys())[0]
        used_slots[limit] = used_slots.get(limit, 0) + used_flow_slot[limit]

    return {label: limit - used_slots[label] for label, limit in limits.items()}
