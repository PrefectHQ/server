from typing import Any

from graphql import GraphQLResolveInfo

from prefect import api
from prefect_server.utilities.graphql import mutation


@mutation.field("write_run_logs")
async def resolve_write_run_logs(
    obj: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    logs = []
    for log in input["logs"]:
        logs.append(
            dict(
                flow_run_id=log.get("flow_run_id", None),
                task_run_id=log.get("task_run_id", None),
                timestamp=log.get("timestamp"),
                message=log.get("message"),
                name=log.get("name"),
                level=log.get("level"),
                info=log.get("info"),
            )
        )
    await api.logs.create_logs(logs)
    return {"success": True}
