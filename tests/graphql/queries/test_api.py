import os

import prefect
import prefect_server

QUERY = """
    query {
        api {
            backend
            mode
            version
            release_timestamp
        }
    }
"""


async def test_backend(run_query):
    result = await run_query(query=QUERY)
    assert result.data.api.backend == "SERVER"


async def test_mode(run_query):
    result = await run_query(query=QUERY)
    assert result.data.api.mode == "normal"


async def test_server_version_picks_up_dunder_version_if_no_server_env_var(
    run_query, monkeypatch
):
    if "PREFECT_SERVER_VERSION" in os.environ:
        monkeypatch.delenv("PREFECT_SERVER_VERSION")

    result = await run_query(query=QUERY)
    assert result.data.api.version == prefect_server.__version__


async def test_server_version_picks_up_env_var(run_query, monkeypatch):
    monkeypatch.setenv("PREFECT_SERVER_VERSION", "server-version")
    result = await run_query(query=QUERY)
    assert result.data.api.version == "server-version"


async def test_release_timestamp_picks_up_env_var(run_query, monkeypatch):
    monkeypatch.setenv("RELEASE_TIMESTAMP", "2020-04-04T01:08:22Z")
    result = await run_query(query=QUERY)
    assert result.data.api.release_timestamp == "2020-04-04T01:08:22Z"


async def test_release_timestamp_returns_null_if_not_set(run_query, monkeypatch):
    if "RELEASE_TIMESTAMP" in os.environ:
        monkeypatch.delenv("RELEASE_TIMESTAMP")
    result = await run_query(query=QUERY)
    assert result.data.api.release_timestamp is None
