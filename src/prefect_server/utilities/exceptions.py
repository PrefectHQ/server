import re
from contextlib import asynccontextmanager
from typing import Optional, Type, TYPE_CHECKING

from graphql import GraphQLError


if TYPE_CHECKING:
    from logging import Logger


class PrefectBackendException(Exception):
    """
    A base exception for Prefect Server and Cloud exceptions
    """

    pass


class APIError(PrefectBackendException):
    # All exceptions of this type include this message for simple parsing from Apollo
    # to attach an API_ERROR code for retries. If modified, the Apollo service should
    # be updated as well.
    __message__ = "Unable to complete operation. An internal API error occurred."

    def __init__(self):
        super().__init__(self.__message__)


class BadRequest(PrefectBackendException):
    pass


class NotFound(PrefectBackendException):
    pass


class ApolloError(GraphQLError, PrefectBackendException):
    """
    Apollo Server-style GraphQL Error
    """

    # the ApolloError's code, which is reported in its output
    code: Optional[str] = None
    # the ApolloError's default message
    message: Optional[str] = None

    def __init__(self, message: str = None, *args, **kwargs):
        if message is None:
            message = self.message

        super().__init__(message=message or "", *args, **kwargs)

        if self.code is not None:
            self.extensions["code"] = self.code


class Unauthenticated(ApolloError):
    code = "UNAUTHENTICATED"
    message = "Unauthenticated"


class Unauthorized(ApolloError):
    code = "FORBIDDEN"
    message = "Unauthorized"


@asynccontextmanager
async def reraise_as_api_error(
    exception_type: Type[Exception],
    match: str = None,
    logger: "Logger" = None,
):
    """
    Capture any exceptions of `exception_type` and reraise them as an `APIError`.
    The full error will be logged with a stack trace if a logger is provided.

    Args:
        exception_type: The exception type to capture
        match: An optional regex string to filter exceptions by
        logger: The logger to use to record the true exception

    Yields:
        None
    """
    try:
        yield
    except exception_type as exc:
        if match and not re.search(match, str(exc), re.IGNORECASE):
            raise
        if logger:
            logger.error(f"Encountered internal API exception: {exc}", exc_info=True)
        raise APIError() from exc
