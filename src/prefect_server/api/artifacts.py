from prefect import models
from prefect.utilities.plugins import register_api


@register_api("artifacts.create_task_run_artifact")
async def create_task_run_artifact(
    task_run_id: str,
    kind: str,
    data: dict,
    tenant_id: str = None,
) -> str:
    """
    Create a task run artifact.

    Args:
        - task_run_id (str): the task run id
        - kind (str): the artifact kind
        - data (dict): the artifact data
        - tenant_id (str, optional): the tenant id that this artifact belongs to. Defaults
            to the tenant ID linked to the task run

    Returns:
        - str: the task run artifact ID
    """
    if not task_run_id:
        raise ValueError("A `task_run_id` must be provided to create artifact")

    task_run = await models.TaskRun.where(id=task_run_id).first({"tenant_id"})

    if not task_run:
        raise ValueError(f"Task run {task_run_id} not found")

    if tenant_id and tenant_id != task_run.tenant_id:
        raise ValueError("Invalid tenant ID.")

    if not tenant_id:
        tenant_id = task_run.tenant_id

    # Insert task run artifact
    return await models.TaskRunArtifact(
        tenant_id=tenant_id, task_run_id=task_run_id, kind=kind, data=data
    ).insert()


@register_api("artifacts.update_task_run_artifact")
async def update_task_run_artifact(
    task_run_artifact_id: str,
    data: dict,
) -> bool:
    """
    Update a task run artifact.

    Args:
        - task_run_artifact_id (str): the task run artifact id
        - data (dict): the artifact data

    Returns:
        - bool: if the update was successful
    """
    if not task_run_artifact_id:
        raise ValueError("Must supply a valid task run artifact ID to update")

    result = await models.TaskRunArtifact.where(id=task_run_artifact_id).update(
        set={"data": data}
    )
    return bool(result.affected_rows)  # type: ignore


@register_api("artifacts.delete_task_run_artifact")
async def delete_task_run_artifact(
    task_run_artifact_id: str,
) -> bool:
    """
    Delete a task run artifact.

    Args:
        - task_run_artifact_id (str): the task run artifact id

    Returns:
        - bool: if the deletion was successful
    """
    if not task_run_artifact_id:
        raise ValueError("Must supply a valid task run artifact ID to delete")

    result = await models.TaskRunArtifact.where(id=task_run_artifact_id).delete()
    return bool(result.affected_rows)  # type: ignore
