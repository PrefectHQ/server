from prefect import models
from prefect.utilities.plugins import register_api


@register_api("artifacts.create_task_run_artifact")
async def create_task_run_artifact(
    task_run_id: str,
    kind: str,
    data: dict,
    tenant_id: str = None,
) -> str:
    """"""
    task_run = await models.TaskRun.where(id=task_run_id).first({"tenant_id"})

    if not task_run:
        raise ValueError(f"Creating artifact failed for task run ID {task_run_id}")

    if not tenant_id:
        tenant_id = task_run.tenant_id

    # Insert task run artifact
    return await models.TaskRunArtifact(
        tenant_id=tenant_id, task_run_id=task_run_id, kind=kind, data=data
    ).insert()
