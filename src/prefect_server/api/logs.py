import uuid
from typing import Any, Dict, List

import pendulum
import pydantic

from prefect import models
from prefect.utilities.plugins import register_api


@register_api("logs.create_logs")
async def create_logs(logs: List[Dict[str, Any]]) -> str:
    """
    Inserts log record(s) into the database.
    Args:
        - logs (list): a list of log records represented as dictionaries, containing the following keys:
            `tenant_id` and `flow_run_id` and optionally containing task_run_id, timestamp, message, name, level and info.

    Returns:
        - None
    """
    model_logs = []
    now = pendulum.now("UTC")
    for log in logs:

        ## create model objects
        try:
            mlog = models.Log(
                id=log.get("id", str(uuid.uuid4())),
                tenant_id=log.get("tenant_id"),
                flow_run_id=log.get("flow_run_id"),
                task_run_id=log.get("task_run_id"),
                timestamp=str(log.get("timestamp") or now),
                message=log.get("message"),
                name=log.get("name"),
                level=log.get("level") or "INFO",
                info=log.get("info"),
                is_loaded_from_archive=log.get("is_loaded_from_archive", False),
            )
        except pydantic.ValidationError:
            continue

        model_logs.append(mlog)

    if model_logs:
        await models.Log.insert_many(model_logs, selection_set={"affected_rows"})
