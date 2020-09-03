import asyncio
from unittest.mock import MagicMock

import pytest
import uvicorn
from asynctest import CoroutineMock
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from prefect import api, models
from prefect.engine.state import Failed, Running, Success
from prefect_server import config
from prefect_server.utilities import tests


class TestCreateCloudHook:
    mutation = """
        mutation($input: create_cloud_hook_input!) {
            create_cloud_hook(input: $input) {
                id
            }
        }
    """

    async def test_create_hook(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config={"url": "test-url"},
                    states=["FAILED"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"tenant_id", "config", "version_group_id", "states", "type", "name"}
        )
        assert hook.tenant_id == tenant_id
        assert hook.config == {"url": "test-url"}
        assert hook.version_group_id is None
        assert hook.states == ["FAILED"]
        assert hook.name is None
        assert hook.type == "WEBHOOK"

    async def test_create_slack_hook(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="SLACK_WEBHOOK",
                    config={"url": "test-url"},
                    states=["FAILED"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"config", "type"}
        )
        assert hook.config == {"url": "test-url"}
        assert hook.type == "SLACK_WEBHOOK"

    async def test_create_prefect_message_hook(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="PREFECT_MESSAGE",
                    config={},
                    states=["FAILED"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"type"}
        )
        assert hook.type == "PREFECT_MESSAGE"

    async def test_create_twilio_hook(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="TWILIO",
                    config={
                        "account_sid": "test_sid",
                        "auth_token": "test_auth_token",
                        "messaging_service_sid": "test_messaging_service_sid",
                        "to": ["+15555555555"],
                    },
                    states=["FAILED"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"config", "type"}
        )
        assert hook.config == {
            "account_sid": "test_sid",
            "auth_token": "test_auth_token",
            "messaging_service_sid": "test_messaging_service_sid",
            "to": ["+15555555555"],
        }
        assert hook.type == "TWILIO"

    async def test_create_pagerduty_hook(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="PAGERDUTY",
                    config={
                        "api_token": "test_api_token",
                        "routing_key": "test_routing_key",
                        "severity": "info",
                    },
                    states=["FAILED"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"config", "type"}
        )
        assert hook.config == {
            "api_token": "test_api_token",
            "routing_key": "test_routing_key",
            "severity": "info",
        }
        assert hook.type == "PAGERDUTY"

    async def test_create_webhook_with_options(self, run_query, tenant_id, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config={"url": "test-url"},
                    version_group_id=flow.version_group_id,
                    states=["Running"],
                    name="test-name",
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"config", "version_group_id", "states", "name"}
        )

        assert hook.config == {"url": "test-url"}
        assert hook.version_group_id == flow.version_group_id
        assert hook.states == ["RUNNING"]
        assert hook.name == "test-name"

    async def test_create_webhook_with_case_insensitive_states(
        self, run_query, tenant_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config={"url": "test-url"},
                    states=["RUNNING"],
                )
            ),
        )

    async def test_create_webhook_with_repeated_states(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config={"url": "test-url"},
                    states=["RUNNING", "RUNNING", "Running", "Running", "Pending"],
                )
            ),
        )

        hook = await models.CloudHook.where(id=result.data.create_cloud_hook.id).first(
            {"states"}
        )

        assert set(hook.states) == {"RUNNING", "PENDING"}

    async def test_webhook_with_invalid_states_fails(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config={"url": "test-url"},
                    states=["Running", "xyz"],
                    name="test-name",
                )
            ),
        )

        assert not result.data.create_cloud_hook
        assert "Invalid state" in result.errors[0].message


class TestDeleteWebhook:
    mutation = """
        mutation($input: delete_cloud_hook_input!) {
            delete_cloud_hook(input: $input) {
                success
            }
        }
    """

    async def test_delete_hook(self, run_query, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(cloud_hook_id=hook_id))
        )

        assert result.data.delete_cloud_hook.success
        assert not await models.CloudHook.where(id=hook_id).first()


class TestSetCloudHookActive:
    mutation = """
            mutation($input: set_cloud_hook_active_input!) {
                set_cloud_hook_active(input: $input) {
                    success
                }
            }
        """

    async def test_set_hook_active(self, run_query, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )
        await api.cloud_hooks.set_cloud_hook_inactive(hook_id)

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(cloud_hook_id=hook_id))
        )

        hook = await models.CloudHook.where(id=hook_id).first({"active"})
        assert hook.active is True


class TestSetInactive:
    mutation = """
            mutation($input: set_cloud_hook_inactive_input!) {
                set_cloud_hook_inactive(input: $input) {
                    success
                }
            }
        """

    async def test_set_hook_inactive(self, run_query, tenant_id):

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(cloud_hook_id=hook_id))
        )

        hook = await models.CloudHook.where(id=hook_id).first({"active"})
        assert hook.active is False


class TestTestWebhook:
    mutation = """
        mutation($input: test_cloud_hook_input!) {
            test_cloud_hook(input: $input) {
                success
                error
            }
        }
    """

    async def test_testing_invalid_hook_returns_error(self, run_query, tenant_id):

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test.test"),
            states=["FAILED"],
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(cloud_hook_id=hook_id))
        )

        assert result.data.test_cloud_hook.success is False
        assert "No scheme included in URL." in result.data.test_cloud_hook.error

    async def test_test_hook(self, run_query, tenant_id, cloud_hook_mock):

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(cloud_hook_id=hook_id))
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        event = call_args[1]["json"]["event"]
        assert event["type"] == "FlowRunStateChange"
        assert event["is_test_event"] is True
        assert event["state"]["state"] == "Success"
        assert event["id"] == call_args[1]["headers"]["X-PREFECT-EVENT-ID"]

    async def test_test_hook_while_specifying_flow_run_id(
        self, run_query, tenant_id, flow_run_id, cloud_hook_mock
    ):

        await asyncio.sleep(0.1)

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["SUCCESS"],
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(cloud_hook_id=hook_id, flow_run_id=flow_run_id)),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        event = call_args[1]["json"]["event"]
        assert event["type"] == "FlowRunStateChange"
        assert event["flow_run"]["id"] == flow_run_id
        assert event["state"]["state"] == "Success"
        assert event["id"] == call_args[1]["headers"]["X-PREFECT-EVENT-ID"]

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_webhook_with_custom_state(
        self, run_query, tenant_id, state_type, cloud_hook_mock
    ):

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(cloud_hook_id=hook_id, state_type=state_type)),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        event = call_args[1]["json"]["event"]
        assert event["state"]["state"] == state_type.capitalize()
        assert (
            event["state"]["serialized_state"]["message"]
            == f"Test {state_type.lower()} state"
        )

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_slack_cloud_hook(
        self, run_query, tenant_id, state_type, cloud_hook_mock
    ):

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="SLACK_WEBHOOK",
            config={"url": "http://0.0.0.0:8100/hook"},
            states=["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"],
        )

        await run_query(
            query=self.mutation,
            variables=dict(input=dict(cloud_hook_id=hook_id, state_type=state_type)),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        blocks = call_args[1]["json"]["blocks"]

        assert blocks[1]["text"]["text"] == f"*State:* `{state_type.title()}`"
        assert (
            blocks[2]["text"]["text"] == f"*Message:* Test {state_type.lower()} state"
        )

    async def test_test_slack_cloud_hook_while_specifying_flow_run_id(
        self, run_query, tenant_id, flow_run_id, cloud_hook_mock
    ):

        # sleep to "flush" the attempt to run cloud hooks on the scheduled
        # state due to asyncio delays
        await asyncio.sleep(0.1)

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="SLACK_WEBHOOK",
            config={"url": "http://0.0.0.0:8100/hook"},
            states=["SUCCESS"],
        )

        await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    cloud_hook_id=hook_id, flow_run_id=flow_run_id, state_type="SUCCESS"
                )
            ),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        blocks = call_args[1]["json"]["blocks"]
        assert blocks[1]["text"]["text"] == f"*State:* `{'SUCCESS'.title()}`"
        assert blocks[2]["text"]["text"] == f"*Message:* Test {'SUCCESS'.lower()} state"

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_prefect_message_webhook(
        self, run_query, tenant_id, flow_run_id, state_type
    ):
        await models.Message.where().delete()

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PREFECT_MESSAGE",
            states=[state_type],
            config=dict(),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(cloud_hook_id=hook_id, state_type=state_type)),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        messages = await models.Message.where({"tenant_id": {"_eq": tenant_id}}).get()
        assert len(messages) == 1

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_prefect_message_webhook_while_specifying_flow_run_id(
        self, run_query, tenant_id, flow_run_id, state_type
    ):
        await models.Message.where().delete()

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PREFECT_MESSAGE",
            states=[state_type],
            config=dict(),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    cloud_hook_id=hook_id,
                    flow_run_id=flow_run_id,
                    state_type=state_type,
                )
            ),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        messages = await models.Message.where({"tenant_id": {"_eq": tenant_id}}).get()
        assert len(messages) == 1

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_twilio_cloud_hook(
        self, run_query, tenant_id, flow_id, flow_run_id, monkeypatch, state_type
    ):
        post_mock = CoroutineMock()
        client = MagicMock(post=post_mock)
        monkeypatch.setattr(
            "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
        )

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="TWILIO",
            states=[state_type],
            config=dict(
                account_sid="test_sid",
                auth_token="test_auth_token",
                messaging_service_sid="test_messaging_service_sid",
                to=["+15555555555"],
            ),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    cloud_hook_id=hook_id,
                    flow_run_id=flow_run_id,
                    state_type=state_type,
                )
            ),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        flow = await models.Flow.where(id=flow_id).first({"name"})
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"id", "name"})
        post_mock.assert_called_with(
            "https://api.twilio.com/2010-04-01/Accounts/test_sid/Messages.json",
            auth=("test_sid", "test_auth_token"),
            data={
                "To": "+15555555555",
                "From": "test_messaging_service_sid",
                "Body": f"Run {flow_run.name} of flow {flow.name} entered a new state: {state_type.title()}. \n Link: {config.api.url}/{tenant.slug}/flow-run/{flow_run.id}",
            },
            timeout=2,
        )

    @pytest.mark.parametrize(
        "state_type", ["SUBMITTED", "SCHEDULED", "RUNNING", "SUCCESS", "FAILED"]
    )
    async def test_test_pagerduty_cloud_hook(
        self, run_query, tenant_id, flow_id, flow_run_id, monkeypatch, state_type
    ):
        post_mock = CoroutineMock()
        client = MagicMock(post=post_mock)
        monkeypatch.setattr(
            "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
        )

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PAGERDUTY",
            states=[state_type],
            config={
                "api_token": "test_api_token",
                "routing_key": "test_routing_key",
                "severity": "info",
            },
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    cloud_hook_id=hook_id,
                    flow_run_id=flow_run_id,
                    state_type=state_type,
                )
            ),
        )
        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        flow = await models.Flow.where(id=flow_id).first({"name"})
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"id", "name"})

        args, kwargs = post_mock.call_args
        assert args == ("https://events.pagerduty.com/v2/enqueue",)
        assert kwargs["headers"] == {"Authorization": "Token token=test_api_token"}
        msg = kwargs["json"]
        payload = msg["payload"]
        assert msg["routing_key"] == "test_routing_key"
        assert payload["severity"] == "info"
        assert payload["custom_details"]["state"] == state_type.title()
        assert payload["custom_details"]["flow"] == flow.name
        link = f"{config.api.url}/{tenant.slug}/flow-run/{flow_run.id}"
        assert msg["links"] == [{"href": link, "text": f"Flow Run {flow_run.name}"}]


class TestPrefectMessageCloudHook:
    @pytest.mark.parametrize("state", [Running(), Success(), Failed()])
    async def test_prefect_message_cloud_hook(
        self, run_query, flow_run_id, state, tenant_id
    ):
        await models.Message.where().delete()

        cloud_hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PREFECT_MESSAGE",
            config={},
            states=[type(state).__name__],
        )
        set_flow_run_state_mutation = """
            mutation($input: set_flow_run_states_input!) {
                set_flow_run_states(input: $input) {
                    states {
                        id
                        status
                        message
                    }
                }
            }
            """
        await run_query(
            query=set_flow_run_state_mutation,
            variables=dict(
                input=dict(
                    states=[
                        dict(
                            flow_run_id=flow_run_id, version=1, state=state.serialize()
                        )
                    ]
                )
            ),
        )
        await asyncio.sleep(1)
        assert (
            await models.Message.where({"tenant_id": {"_eq": tenant_id}}).count() == 1
        )
