import httpx
import pytest
from box import Box

from prefect_server import config
from prefect_server.services.graphql import app

GRAPHQL_URL = config.services.graphql.path


@pytest.fixture
async def client():
    yield httpx.AsyncClient(app=app, base_url="https://prefect.io")


@pytest.fixture
async def run_query(client):
    async def run_query(query, variables=None, headers=None):
        headers = headers or {}

        response = await client.post(
            GRAPHQL_URL,
            json=dict(query=query, variables=variables or {}),
            headers=headers,
        )
        result = Box(response.json())
        return result

    return run_query
