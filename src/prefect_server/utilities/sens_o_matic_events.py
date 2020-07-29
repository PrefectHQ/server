import asyncio
import functools
import uuid
from typing import Callable

import httpx

from prefect_server.configuration import config
from prefect_server.utilities.logging import get_logger

sens_o_matic_httpx_client = httpx.AsyncClient()

__all__ = ("emit_delete_event", "register_delete", "sens_o_matic_httpx_client")


async def emit_delete_event(row_id: str, table_name: str) -> dict:
    env = config.env
    logger = get_logger("sens-o-matic")

    if env == "local":
        return None

    try:
        event_id = str(uuid.uuid4())
        payload = {"cloud_environment": env, "row_id": row_id, "table_name": table_name}
        event = {
            "id": event_id,
            "source": "prefect_server",
            "type": "delete",
            "payload": payload,
        }
        result = await sens_o_matic_httpx_client.post(
            "https://sens-o-matic.prefect.io/",
            json=event,
            headers={"X-PREFECT-EVENT": "prefect_server-0.0.1"},
            timeout=10,
        )
        logger.debug("Delete event sent to sens-o-matic: %s", str(result))
    except Exception as e:
        # Log the information that we were trying to send to sens-o-matic so Dylan can backfill
        logger.error(
            "Error during attempt to send event to sens-o-matic: %s", str(event)
        )
        logger.error(e)

    return event


def register_delete(table_name: str, id_key: str) -> Callable:
    """
    Decorator for a graphql resolver for automatically emitting delete events to the sens-o-matic.

    Parameters
    ----------
    table_name : str
        The name of the table from which a row was just deleted
    id_key : str
        The key in the GraphQL input argument containing the id field for the deleted row
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(obj, info, input):
            result = await func(obj, info, input)
            successful = result.get("success", False)

            if not successful:
                return result

            deleted_row_id = input.get(id_key, None)

            asyncio.create_task(
                emit_delete_event(row_id=deleted_row_id, table_name=table_name)
            )

            return result

        return wrapper

    return decorator
