from prefect_server.database import models
from prefect.utilities.plugins import register_api


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
async def delete_flow_concurrency_limit(flow_concurrency_limit_id: str) -> bool:
    """
    Deletes a flow concurrency limit.

    Args:
        - flow_concurrency_limit_id (str): The flow concurrency limit
            to delete.

    Returns:
        - bool: If the delete was successful

    Raises:
        - ValueError: If an ID isn't provided
    """

    if not flow_concurrency_limit_id:
        raise ValueError("Invalid flow concurrency limit ID.")

    result = await models.FlowConcurrencyLimit.where(
        id=flow_concurrency_limit_id
    ).delete()
    return bool(result.affected_rows)

