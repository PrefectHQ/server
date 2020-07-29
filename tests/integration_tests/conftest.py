import os

import httpx
import pytest
from box import Box

import prefect
import prefect_server
from prefect.client import Client
from prefect.utilities.configuration import set_temporary_config
from prefect_server import config
from prefect_server.services.graphql import app

GRAPHQL_URL = config.services.graphql.path


def pytest_collection_modifyitems(items):
    """
    Modify items below `tests/integration_tests` to have the integration_test flag
    """
    integration_tests_directory = os.path.dirname(__file__)
    for item in items:
        if integration_tests_directory in str(item.fspath):
            item.add_marker(pytest.mark.integration_test)


@pytest.fixture
def client(project_id):
    yield Client()


@pytest.fixture(autouse=True, scope="session")
def set_config():
    services = prefect_server.config.services
    config = {"cloud.graphql": f"http://{services.apollo.host}:{services.apollo.port}"}
    with set_temporary_config(config):
        prefect.utilities.logging.configure_logging()
        yield


@pytest.fixture
async def python_graphql_client():
    yield httpx.AsyncClient(app=app, base_url="http://prefect.io")


@pytest.fixture
async def run_graphql_query(python_graphql_client):
    async def run_query(query, variables=None, headers=None):
        response = await python_graphql_client.post(
            GRAPHQL_URL,
            json=dict(query=query, variables=variables or {}),
            headers=headers or {},
        )
        result = Box(response.json())
        return result

    return run_query
