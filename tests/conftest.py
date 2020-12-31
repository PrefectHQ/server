import asyncio
import inspect
from unittest.mock import MagicMock

import pytest
from asynctest import CoroutineMock

from .fixtures.database_fixtures import *
from prefect_server.utilities import context


def pytest_collection_modifyitems(session, config, items):
    """
    Modify tests prior to execution
    """
    for item in items:
        # automatically add @pytest.mark.asyncio to async tests
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(
            item.function
        ):
            item.add_marker(pytest.mark.asyncio)


# redefine the event loop to support module-scoped fixtures
# https://github.com/pytest-dev/pytest-asyncio/issues/68
@pytest.yield_fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def flow_concurrency_lock():

    with context.set_context(flow_concurrency_lock=asyncio.Semaphore()):
        yield


@pytest.fixture
def cloud_hook_mock(monkeypatch):
    post_mock = CoroutineMock()
    monkeypatch.setattr(
        "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
    )
    return post_mock
