from prefect import models
from prefect.utilities.plugins import register_api

PREFECT_MESSAGE_TYPES = {"CLOUD_HOOK", "REQUIRES_APPROVAL"}


@register_api("messages.create_message")
async def create_message(
    type: str, content: dict, tenant_id: str, text: str = None
) -> str:
    if type not in PREFECT_MESSAGE_TYPES:
        raise ValueError("Invalid message type.")

    return await models.Message(
        tenant_id=tenant_id,
        type=type,
        text=text,
        content=content,
    ).insert()


@register_api("messages.create_requires_approval_message")
async def create_requires_approval_message(task_run: models.TaskRun) -> None:
    """
    Creates a REQUIRES_APPROVAL message
    """

    tenant_id = task_run.tenant_id
    if not tenant_id:
        raise ValueError("Invalid tenant ID.")

    flow_run_id = task_run.flow_run_id

    flow_run = await models.FlowRun.get_one(task_run.flow_run_id)

    # Create the message content, which should include:
    # The message type (REQUIRES_APPROVAL)
    # Task run information (task and task_run_id)
    # Flow run information (flow_run and flow_run_id)
    # Flow information (included in the flow_run model)
    message_content = {
        "type": "REQUIRES_APPROVAL",
        "task_run_id": task_run.id,
        "task_run": task_run,
        "flow_run_id": task_run.flow_run_id,
        "flow_run": flow_run,
        "tenant_id": tenant_id,
    }

    await create_message(
        tenant_id=tenant_id,
        type="REQUIRES_APPROVAL",
        content=message_content,
    )


@register_api("messages.mark_message_as_read")
async def mark_message_as_read(message_id: str) -> bool:
    if not message_id:
        raise ValueError("Invalid message ID.")
    result = await models.Message.where(id=message_id).update(set=dict(read=True))
    return bool(result.affected_rows)  # type:ignore


@register_api("messages.mark_message_as_unread")
async def mark_message_as_unread(message_id: str) -> bool:
    if not message_id:
        raise ValueError("Invalid message ID.")
    result = await models.Message.where(id=message_id).update(set=dict(read=False))
    return bool(result.affected_rows)  # type:ignore


@register_api("messages.delete_message")
async def delete_message(message_id: str) -> bool:
    if not message_id:
        raise ValueError("Invalid message ID.")
    result = await models.Message.where(id=message_id).delete()
    return bool(result.affected_rows)  # type:ignore
