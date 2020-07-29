import os

import prefect
import prefect_server


async def test_unauthenticated(run_query):
    query = """
        query {
            reference_data {
                state_hierarchy
            }
        }
    """
    result = await run_query(query=query)
    for s in result.data.reference_data.state_hierarchy.keys():
        assert issubclass(getattr(prefect.engine.state, s), prefect.engine.state.State)
    assert set(result.data.reference_data.state_hierarchy["Success"]) == {
        "Success",
        "Skipped",
        "Mapped",
        "Cached",
    }


async def test_state_hierarchy(run_query):
    query = """
        query {
            reference_data {
                state_hierarchy
            }
        }
    """
    result = await run_query(query=query)
    for s in result.data.reference_data.state_hierarchy.keys():
        assert issubclass(getattr(prefect.engine.state, s), prefect.engine.state.State)
    assert set(result.data.reference_data.state_hierarchy["Success"]) == {
        "Success",
        "Skipped",
        "Mapped",
        "Cached",
    }


async def test_state_info(run_query):
    query = """
        query {
            reference_data {
                state_info
            }
        }
    """
    result = await run_query(query=query)
    for state_name, info in result.data.reference_data.state_info.items():
        state = getattr(prefect.engine.state, state_name)
        assert state.color == info["color"]
