import uuid
from asyncio import sleep
from unittest.mock import MagicMock

import pytest
from asynctest import CoroutineMock

from prefect_server.utilities.sens_o_matic_events import emit_delete_event
from prefect_server.utilities.tests import (
    evaluate_delete_event_payload,
    set_temporary_config,
)


class TestEmitDeleteEvent:
    async def test_event_payload_is_formed_properly(self, sens_o_matic_httpx_mock):

        with set_temporary_config("env", "production"):
            row_id = str(uuid.uuid4())
            table_name = "test"

            result = await emit_delete_event(row_id=row_id, table_name=table_name)

        await sleep(0)
        evaluate_delete_event_payload(
            table_name=table_name, row_id=row_id, post_mock=sens_o_matic_httpx_mock
        )

    async def test_exceptions_are_logged_and_not_thrown(self, monkeypatch):
        # Mock httpx
        post_mock = CoroutineMock()
        post_mock.side_effect = Exception("Boom! I'm testing an exception!")
        httpx_mock = MagicMock()

        async def post(*args, **kwargs):
            post_mock(*args, **kwargs)

        httpx_mock.post = post
        monkeypatch.setattr(
            "prefect_server.utilities.sens_o_matic_events.sens_o_matic_httpx_client",
            httpx_mock,
        )

        with set_temporary_config("env", "production"):
            try:
                row_id = str(uuid.uuid4())
                table_name = "test"

                result = await emit_delete_event(row_id=row_id, table_name=table_name)
            except Exception as e:
                pytest.fail("Unexpected error")

        await sleep(0)
        assert post_mock.call_args[0][0] == "https://sens-o-matic.prefect.io/"

    async def test_event_payload_does_not_fire_for_local_env(
        self, sens_o_matic_httpx_mock
    ):
        result = False

        with set_temporary_config("env", "local"):
            row_id = str(uuid.uuid4())
            table_name = "test"

            result = await emit_delete_event(row_id=row_id, table_name=table_name)

        await sleep(0)
        assert result is None
        assert sens_o_matic_httpx_mock.called is False
