import os

import pytest

from prefect_server import config
from prefect_server.services.agents.local_agent import LocalAgent
from prefect_server.utilities.graphql import GraphQLClient


def pytest_collection_modifyitems(items):
    """
    Modify items below `tests/service_tests` to have the service_test flag
    """
    service_tests_directory = os.path.dirname(__file__)
    for item in items:
        if service_tests_directory in str(item.fspath):
            item.add_marker(pytest.mark.service_test)


@pytest.fixture()
def agent():
    yield LocalAgent()


@pytest.fixture()
async def run_apollo_query():
    async def run_apollo_query(query, variables=None, headers=None):
        headers = headers or {}

        client = GraphQLClient(
            url=f"http://{config.services.apollo.host}:{config.services.apollo.port}"
        )

        result = await client.execute(
            query=query,
            variables=variables or {},
            headers=headers,
            raise_on_error=False,
        )
        return result

    return run_apollo_query
