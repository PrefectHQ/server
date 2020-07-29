import inspect
import textwrap
import traceback
from typing import Any

from ariadne.types import Extension
from graphql import GraphQLResolveInfo

from prefect_server import config
from prefect_server.utilities import context, logging

logger = logging.get_logger("GraphQL")


def log_error(exc: Exception) -> None:
    ctx = context.get_context()
    ctx.pop("auth_token", None)
    if config.env == "local":
        logger.error(
            textwrap.dedent(
                f"""
                An application error occurred:

                ### --- Error ------------------------------

                {textwrap.indent(traceback.format_exc(), "        ")}

                ### --- Context ------------------------------

                {textwrap.indent(str(ctx), "        ")}

                """
            )
        )
    else:
        logger.error({"traceback": traceback.format_exc(), "context": ctx})


class PrefectHeader(Extension):
    async def resolve(
        self, next_, parent: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any
    ) -> Any:
        request_headers = info.context.get("request", {}).get("headers", {})
        # construct a dict, since they come in as a list of tuples
        headers_dict = {}
        for header in request_headers:
            if header[0].decode().lower().startswith("x-prefect"):
                headers_dict.update({header[0].decode().lower(): header[1].decode()})
        with context.set_context(headers=headers_dict):
            result = next_(parent, info, *args, **kwargs)
            if inspect.iscoroutine(result):
                result = await result

        return result
