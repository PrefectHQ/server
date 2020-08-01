from typing import Any

from graphql import GraphQLResolveInfo

from prefect import api
from prefect_server.utilities.graphql import mutation


@mutation.field("mark_message_as_read")
async def resolve_mark_message_as_read(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.messages.mark_message_as_read(
            message_id=input["message_id"]
        )
    }


@mutation.field("mark_message_as_unread")
async def resolve_mark_message_as_unread(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.messages.mark_message_as_unread(
            message_id=input["message_id"]
        )
    }


@mutation.field("delete_message")
async def resolve_delete_message(
    parent: Any, info: GraphQLResolveInfo, input: dict
) -> dict:
    return {
        "success": await api.messages.delete_message(message_id=input["message_id"])
    }
