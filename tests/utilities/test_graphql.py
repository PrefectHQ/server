import pytest
from unittest.mock import MagicMock

from prefect_server.utilities.graphql import GraphQLClient
from prefect_server.utilities.exceptions import APIError


async def test_graphql_client_connection_errors_reraised(monkeypatch):
    mock = MagicMock(side_effect=ValueError("Failed to connect to foo"))
    monkeypatch.setattr("prefect_server.utilities.graphql.httpx_client.post", mock)
    with pytest.raises(APIError):
        await GraphQLClient("localhost").execute(query="query { tenant { id } }")
