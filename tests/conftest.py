import asyncio
import inspect
from unittest.mock import MagicMock

import pytest
from asynctest import CoroutineMock

from .fixtures.database_fixtures import *


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


@pytest.fixture
def cloud_hook_mock(monkeypatch):
    post_mock = CoroutineMock()
    monkeypatch.setattr(
        "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
    )
    return post_mock


@pytest.fixture(autouse=True)
def finish_background_scheduling(event_loop):
    """
    Scheduling flow runs happens in the background, which means tests
    can complete before it even starts. This prints an asyncio debug
    error. This fixture cancels those background scheduling tasks.
    """
    try:
        yield
    finally:
        for task in asyncio.all_tasks(event_loop):
            if task._coro.__name__ == "schedule_flow_runs":
                task.cancel()
