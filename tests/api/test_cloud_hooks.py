import asyncio
import uuid
from unittest.mock import MagicMock

import pendulum
import pytest
import uvicorn
from asynctest import CoroutineMock
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

import prefect
from prefect import api, models
from prefect_server import config
from prefect_server.utilities import events, exceptions, tests

# -----------------------------------------------------------
# Tests
# -----------------------------------------------------------


class TestCreateHook:
    async def test_create_hook(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        hook = await models.CloudHook.where(id=hook_id).first(
            {"type", "config", "version_group_id", "states", "active", "name"}
        )
        assert hook.type == "WEBHOOK"
        assert hook.config == {"url": "test-url"}
        assert hook.version_group_id is None
        assert hook.states == ["FAILED"]
        assert hook.name is None

    async def test_create_named_hook(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
            name="test-name",
        )

        hook = await models.CloudHook.where(id=hook_id).first({"name"})
        assert hook.name == "test-name"

    async def test_hook_cascades_when_tenant_deleted(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )
        await models.Tenant.where().delete()
        assert not await models.CloudHook.where(id=hook_id).first()

    async def test_create_hook_with_invalid_tenant_id_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Foreign key violation"):
            await api.cloud_hooks.create_cloud_hook(
                tenant_id=str(uuid.uuid4()),
                type="WEBHOOK",
                config=dict(url="test-url"),
                states=["FAILED"],
            )

    async def test_create_hook_with_no_tenant_id_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid tenant ID"):
            await api.cloud_hooks.create_cloud_hook(
                tenant_id=None,
                type="WEBHOOK",
                config=dict(url="test-url"),
                states=["FAILED"],
            )

    async def test_create_hook_with_version_group_id(self, tenant_id, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
            version_group_id=flow.version_group_id,
        )

        hook = await models.CloudHook.where(id=hook_id).first({"version_group_id"})
        assert hook.version_group_id == flow.version_group_id

    async def test_create_hook_with_states(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running", "Pending"],
        )

        hook = await models.CloudHook.where(id=hook_id).first({"states"})
        # always capitalized
        assert set(hook.states) == {"RUNNING", "PENDING"}

    async def test_create_hook_with_invalid_type_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid cloud hook type"):
            hook_id = (
                await api.cloud_hooks.create_cloud_hook(
                    tenant_id=tenant_id, type="bad-type", config=None, states=["FAILED"]
                ),
            )

    @pytest.mark.parametrize("config", [None, dict(url=1, other=2), dict()])
    async def test_create_webhook_with_invalid_config_fails(self, tenant_id, config):
        with pytest.raises(ValueError, match="Invalid config"):
            hook_id = (
                await api.cloud_hooks.create_cloud_hook(
                    tenant_id=tenant_id,
                    type="WEBHOOK",
                    config=config,
                    states=["FAILED"],
                ),
            )

    async def test_create_hook_with_invalid_states_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid states"):
            hook_id = await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id,
                type="WEBHOOK",
                config=dict(url="test-url"),
                states=["Running", "Pending", "test-url"],
            )

    async def test_create_hook_with_string_state_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid states"):
            hook_id = await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id,
                type="WEBHOOK",
                config=dict(url="test-url"),
                states="Running",
            )

    async def test_create_hook_with_empty_list_states_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid states"):
            hook_id = await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id,
                type="WEBHOOK",
                config=dict(url="test-url"),
                states=[],
            )


class TestCreateSlackWebhook:
    async def test_create_hook(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="SLACK_WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        hook = await models.CloudHook.where(id=hook_id).first({"type", "config"})
        assert hook.type == "SLACK_WEBHOOK"
        assert hook.config == {"url": "test-url"}

    @pytest.mark.parametrize("config", [None, {}, {"url": "test-url", "x": 1}])
    async def test_create_hook_bad_config(self, tenant_id, config):
        with pytest.raises(ValueError, match="Invalid config"):
            hook_id = await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id,
                type="SLACK_WEBHOOK",
                config=config,
                states=["FAILED"],
            )


class TestCreateTwilioWebhook:
    async def test_create_hook(self, tenant_id):
        cloud_hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="TWILIO",
            config=dict(
                account_sid="test_sid",
                auth_token="test_auth_token",
                messaging_service_sid="test_messaging_service_sid",
                to=["+1555555555"],
            ),
            states=["FAILED"],
        )

        hook = await models.CloudHook.where(id=cloud_hook_id).first(
            {"type", "tenant_id", "config"}
        )
        assert hook.type == "TWILIO"
        assert hook.tenant_id == tenant_id
        assert hook.config["account_sid"] == "test_sid"
        assert hook.config["auth_token"] == "test_auth_token"
        assert hook.config["messaging_service_sid"] == "test_messaging_service_sid"
        assert hook.config["to"] == ["+1555555555"]

    @pytest.mark.parametrize(
        "config",
        [
            None,
            {},
            {"auth_token": "a", "messaging_service_sid": "b", "to": ["555"]},
            {"account_sid": "a", "messaging_service_sid": "b", "to": ["555"]},
            {"account_sid": "a", "auth_token": "b", "to": ["555"]},
            {"account_sid": "a", "auth_token": "b", "messaging_service_sid": "c"},
            {
                "account_sid": "a",
                "auth_token": "b",
                "messaging_service_sid": "c",
                "to": [],
            },
        ],
    )
    async def test_create_hook_with_bad_config(self, tenant_id, config):
        with pytest.raises(ValueError, match="Invalid config"):
            await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id, type="TWILIO", config=config, states=["FAILED"]
            )


class TestCreatePrefectNotificationWebhook:
    async def test_create_hook(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id, type="PREFECT_MESSAGE", config={}, states=["FAILED"]
        )

        hook = await models.CloudHook.where(id=hook_id).first({"type", "config"})
        assert hook.type == "PREFECT_MESSAGE"


class TestCreatePagerDutyWebhook:
    @pytest.mark.parametrize("severity", ["info", "warning", "error", "critical"])
    async def test_create_hook(self, tenant_id, severity):
        config = {
            "api_token": "test_api_token",
            "routing_key": "test_routing_key",
            "severity": severity,
        }
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id, type="PAGERDUTY", config=config, states=["FAILED"]
        )

        hook = await models.CloudHook.where(id=hook_id).first({"type", "config"})
        assert hook.type == "PAGERDUTY"
        assert hook.config == config

    @pytest.mark.parametrize(
        "config",
        [
            {"routing_key": "test_routing_key", "severity": "info"},
            {"api_token": "test_api_token", "severity": "info"},
            {"api_token": "test_api_token", "routing_key": "test_routing_key"},
            {
                "api_token": "test_api_token",
                "routing_key": "test_routing_key",
                "severity": "invalid",
            },
        ],
    )
    async def test_create_hook_bad_config(self, tenant_id, config):
        with pytest.raises(ValueError, match="Invalid config"):
            hook_id = await api.cloud_hooks.create_cloud_hook(
                tenant_id=tenant_id, type="PAGERDUTY", config=config, states=["FAILED"]
            )


class TestDeleteHook:
    async def test_delete_hook(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )
        assert await api.cloud_hooks.delete_cloud_hook(hook_id)

        assert not await models.CloudHook.where(id=hook_id).first()

    async def test_delete_hook_fails_with_invalid_id(self, tenant_id):
        assert not await api.cloud_hooks.delete_cloud_hook(str(uuid.uuid4()))

    async def test_create_hook_with_no_id_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.cloud_hooks.delete_cloud_hook(None)


class TestHookStatus:
    async def test_set_hook_inactive(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        hook = await models.CloudHook.where(id=hook_id).first({"active"})
        assert hook.active is True

        # call multiple times to ensure idempotency
        await api.cloud_hooks.set_cloud_hook_inactive(hook_id)
        await api.cloud_hooks.set_cloud_hook_inactive(hook_id)

        hook = await models.CloudHook.where(id=hook_id).first({"active"})
        assert hook.active is False

    async def test_set_hook_active(self, tenant_id):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["FAILED"],
        )

        # set inactive
        await api.cloud_hooks.set_cloud_hook_inactive(hook_id)
        # set active
        # call multiple times to ensure idempotency
        await api.cloud_hooks.set_cloud_hook_active(hook_id)
        await api.cloud_hooks.set_cloud_hook_active(hook_id)

        hook = await models.CloudHook.where(id=hook_id).first({"active"})
        assert hook.active is True

    async def test_bad_id_active(self, tenant_id):
        assert not await api.cloud_hooks.set_cloud_hook_active(str(uuid.uuid4()))

    async def test_bad_id_inactive(self, tenant_id):
        assert not await api.cloud_hooks.set_cloud_hook_inactive(str(uuid.uuid4()))

    async def test_set_active_hook_with_no_id_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.cloud_hooks.set_cloud_hook_active(None)

    async def test_set_inactive_hook_with_no_id_fails(self, tenant_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.cloud_hooks.set_cloud_hook_inactive(None)


class TestMatchHooks:
    @pytest.fixture(autouse=True)
    def matched_hooks(self, monkeypatch):
        HOOKS = []
        original_get_matching_hooks = api.cloud_hooks._get_matching_hooks

        async def _get_matching_hooks(event: events.Event):
            nonlocal HOOKS
            result = await original_get_matching_hooks(event)
            HOOKS.extend(result)
            return result

        monkeypatch.setattr(
            "prefect_server.api.cloud_hooks._get_matching_hooks", _get_matching_hooks
        )
        return HOOKS

    async def test_matching_hooks(self, tenant_id, flow_run_id, matched_hooks):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running"],
        )

        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id}

    async def test_matching_multiple_hooks(self, tenant_id, flow_run_id, matched_hooks):
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running"],
        )
        hook_id_2 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running"],
        )

        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id_1, hook_id_2}

    async def test_matching_multiple_hooks_only_active(
        self, tenant_id, flow_run_id, matched_hooks
    ):
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running"],
        )
        # set inactive
        await api.cloud_hooks.set_cloud_hook_inactive(hook_id_1)
        hook_id_2 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running"],
        )

        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id_2}

    async def test_matching_respects_version_group_id(
        self, tenant_id, flow_id, flow_run_id, labeled_flow_id, matched_hooks
    ):
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})
        labeled_flow = await models.Flow.where(id=labeled_flow_id).first(
            {"version_group_id"}
        )
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["RUNNING"],
            version_group_id=flow.version_group_id,
        )
        hook_id_2 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["RUNNING"],
            version_group_id=labeled_flow.version_group_id,
        )

        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id_1}

    async def test_matching_respects_states(
        self, tenant_id, flow_run_id, matched_hooks
    ):
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Running", "Failed"],
        )
        hook_id_2 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Scheduled"],
        )

        await api.states.set_flow_run_state(flow_run_id, prefect.engine.state.Running())
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id_1}

    async def test_matching_does_not_respect_state_parents(
        self, tenant_id, flow_run_id, matched_hooks
    ):
        """
        Test that a state matches exactly and not its parent
        """
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Pending"],
        )
        hook_id_2 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["Scheduled"],
        )

        await api.states.set_flow_run_state(
            flow_run_id, prefect.engine.state.Scheduled()
        )
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == {hook_id_2}

    async def test_matching_does_not_respect_state_children(
        self, tenant_id, flow_run_id, matched_hooks
    ):
        """
        Test that a state matches exactly and not its children
        """
        hook_id_1 = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="test-url"),
            states=["TriggerFailed"],
        )
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Failed()
        )
        # sleep to allow hooks to fire
        await asyncio.sleep(0.1)

        assert {h.id for h in matched_hooks} == set()


class TestCallHooks:
    async def test_call_hooks_with_event_payload(
        self, tenant_id, flow_run_id, cloud_hook_mock
    ):
        dt = pendulum.now("utc")
        await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Failed()
        )

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args

        assert call_args[0][0] == "http://0.0.0.0:8100/hook"
        event = call_args[1]["json"]["event"]
        assert event["type"] == "FlowRunStateChange"
        assert dt < pendulum.parse(event["timestamp"]) < pendulum.now()
        assert event["flow_run"]["id"] == flow_run_id
        assert event["state"]["state"] == "Failed"

        assert event["id"] == call_args[1]["headers"]["X-PREFECT-EVENT-ID"]

    async def test_call_hooks_multiple_times(
        self, tenant_id, flow_run_id, cloud_hook_mock
    ):
        await asyncio.sleep(0.25)
        await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["SUBMITTED", "RUNNING", "SUCCESS", "FINISHED"],
        )

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Submitted()
        )
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Running()
        )
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Success()
        )

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        states = set(
            [
                call[1]["json"]["event"]["state"]["state"]
                for call in cloud_hook_mock.call_args_list
            ]
        )
        assert states == {"Submitted", "Running", "Success"}

    async def test_only_call_hook_for_matching_states(
        self, tenant_id, flow_run_id, cloud_hook_mock
    ):
        await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["Submitted", "Running"],
        )

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Submitted()
        )
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Running()
        )
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Success()
        )

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        states = set(
            [
                call[1]["json"]["event"]["state"]["state"]
                for call in cloud_hook_mock.call_args_list
            ]
        )
        assert states == {"Submitted", "Running"}

    async def test_only_call_hook_for_matching_flows(
        self,
        tenant_id,
        flow_run_id,
        flow_id,
        labeled_flow_id,
        labeled_flow_run_id,
        cloud_hook_mock,
    ):
        flow = await models.Flow.where(id=flow_id).first({"version_group_id"})
        await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["SUCCESS"],
            version_group_id=flow.version_group_id,
        )

        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Success()
        )
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id, state=prefect.engine.state.Failed()
        )

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        assert (
            cloud_hook_mock.call_args[1]["json"]["event"]["state"]["state"] == "Success"
        )

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_call_slack_web_hook(
        self, tenant_id, flow_run_id, state, cloud_hook_mock
    ):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="SLACK_WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["RUNNING", "SUCCESS"],
        )

        await api.states.set_flow_run_state(flow_run_id, state=state)

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        blocks = call_args[1]["json"]["blocks"]

        assert "entered a new state" in blocks[0]["text"]["text"]
        assert blocks[1]["text"]["text"].startswith("*State:*")
        assert blocks[2]["text"]["text"].startswith("*Message:")

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_call_prefect_message(self, tenant_id, flow_run_id, state):
        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PREFECT_MESSAGE",
            config={},
            states=["RUNNING", "SUCCESS"],
        )

        await api.states.set_flow_run_state(flow_run_id, state=state)
        await asyncio.sleep(1)

        flow_run_state = await models.FlowRunState.where(
            {
                "_and": [
                    {"flow_run_id": {"_eq": flow_run_id}},
                    {"state": {"_eq": type(state).__name__}},
                ]
            }
        ).first()

        messages = await models.Message.where({"tenant_id": {"_eq": tenant_id}}).get(
            {"type", "content"}
        )
        assert len(messages) == 1
        message = messages[0]
        assert message.type == "CLOUD_HOOK"
        assert message.content["event"]["state"]["state"] == type(state).__name__
        assert message.content["event"]["flow_run"]["id"] == flow_run_id
        assert message.content["event"]["state"]["id"] == flow_run_state.id
        assert message.content["type"] == "CLOUD_HOOK"


class TestTestHooks:
    async def test_test_cloud_hook(self, tenant_id, flow_run_id, cloud_hook_mock):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        await api.cloud_hooks.test_cloud_hook(cloud_hook_id=hook_id)

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        event = call_args[1]["json"]["event"]
        assert event["type"] == "FlowRunStateChange"
        assert event["is_test_event"] is True
        assert event["state"]["state"] == "Success"
        assert event["state"]["serialized_state"]["message"] == f"Test success state"
        assert event["id"] == call_args[1]["headers"]["X-PREFECT-EVENT-ID"]

    @pytest.mark.parametrize(
        "state",
        [
            prefect.engine.state.Running(message="I am Running"),
            prefect.engine.state.Finished(message="I am Finished"),
            prefect.engine.state.Failed(message="I am Failed"),
        ],
    )
    async def test_test_cloud_hook_with_state(
        self, tenant_id, flow_run_id, state, cloud_hook_mock
    ):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        await api.cloud_hooks.test_cloud_hook(cloud_hook_id=hook_id, state=state)

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        call_args = cloud_hook_mock.call_args
        event = call_args[1]["json"]["event"]
        assert event["type"] == "FlowRunStateChange"
        assert event["is_test_event"] is True
        assert event["state"]["state"] == type(state).__name__
        assert (
            event["state"]["serialized_state"]["message"]
            == f"I am {type(state).__name__}"
        )
        assert event["id"] == call_args[1]["headers"]["X-PREFECT-EVENT-ID"]

    async def test_test_cloud_hook_none_id(self, tenant_id, flow_run_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.cloud_hooks.test_cloud_hook(cloud_hook_id=None)

    async def test_test_cloud_hook_invalid_id(self, tenant_id, flow_run_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await api.cloud_hooks.test_cloud_hook(cloud_hook_id=str(uuid.uuid4()))

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_test_slack_web_hook(
        self, tenant_id, flow_run_id, state, cloud_hook_mock
    ):
        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="SLACK_WEBHOOK",
            config=dict(url="http://0.0.0.0:8100/hook"),
            states=["FAILED"],
        )

        await api.cloud_hooks.test_cloud_hook(
            cloud_hook_id=hook_id, flow_run_id=flow_run_id, state=state
        )

        # sleep to give the async webhook a chance to fire
        await asyncio.sleep(1)
        # retrieve the info necessary to validate the link sent
        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})

        call_args = cloud_hook_mock.call_args
        assert call_args[0][0] == "http://0.0.0.0:8100/hook"
        blocks = call_args[1]["json"]["blocks"]
        assert "entered a new state" in blocks[0]["text"]["text"]
        assert blocks[1]["text"]["text"].startswith("*State:*")
        assert blocks[2]["text"]["text"].startswith("*Message:")
        assert (
            blocks[3]["text"]["text"]
            == f"*Link:* {config.api.url}/{tenant.slug}/flow-run/{flow_run_id}"
        )

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_test_prefect_message(self, tenant_id, flow_id, flow_run_id, state):
        cloud_hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PREFECT_MESSAGE",
            config={},
            states=["RUNNING", "SUCCESS"],
        )

        await api.cloud_hooks.test_cloud_hook(
            cloud_hook_id=cloud_hook_id, flow_run_id=flow_run_id, state=state
        )

        message = await models.Message.where({"tenant_id": {"_eq": tenant_id}}).first(
            {"type", "content"}
        )
        assert message.type == "CLOUD_HOOK"
        assert message.content["event"]["state"]["state"] == type(state).__name__
        assert message.content["event"]["flow_run"]["id"] == flow_run_id
        assert message.content["type"] == "CLOUD_HOOK"

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_test_twilio(
        self, tenant_id, flow_id, flow_run_id, state, monkeypatch
    ):
        post_mock = CoroutineMock()
        client = MagicMock(post=post_mock)
        monkeypatch.setattr(
            "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
        )

        cloud_hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="TWILIO",
            config=dict(
                account_sid="test_sid",
                auth_token="test_auth_token",
                messaging_service_sid="test_messaging_service_sid",
                to=["+15555555555"],
            ),
            states=["RUNNING", "SUCCESS"],
        )

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        flow = await models.Flow.where(id=flow_id).first({"name"})
        flow_run = await models.FlowRun.where(id=flow_run_id).first({"id", "name"})

        await api.cloud_hooks.test_cloud_hook(
            cloud_hook_id=cloud_hook_id, flow_run_id=flow_run_id, state=state
        )

        post_mock.assert_called_with(
            "https://api.twilio.com/2010-04-01/Accounts/test_sid/Messages.json",
            auth=("test_sid", "test_auth_token"),
            data={
                "To": "+15555555555",
                "From": "test_messaging_service_sid",
                "Body": f"Run {flow_run.name} of flow {flow.name} entered a new state: {type(state).__name__}. \n Link: {config.api.url}/{tenant.slug}/flow-run/{flow_run.id}",
            },
            timeout=2,
        )

    @pytest.mark.parametrize(
        "state", [prefect.engine.state.Running(), prefect.engine.state.Success()]
    )
    async def test_test_pagerduty(
        self, tenant_id, flow_id, flow_run_id, state, monkeypatch
    ):
        post_mock = CoroutineMock()
        client = MagicMock(post=post_mock)
        monkeypatch.setattr(
            "prefect_server.api.cloud_hooks.cloud_hook_httpx_client.post", post_mock
        )

        hook_id = await api.cloud_hooks.create_cloud_hook(
            tenant_id=tenant_id,
            type="PAGERDUTY",
            config={
                "api_token": "test_api_token",
                "routing_key": "test_routing_key",
                "severity": "info",
            },
            states=["RUNNING", "SUCCESS"],
        )

        await api.cloud_hooks.test_cloud_hook(
            cloud_hook_id=hook_id, flow_run_id=flow_run_id, state=state
        )

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
        assert payload["custom_details"]["state"] == type(state).__name__
        assert payload["custom_details"]["state_message"] == (state.message or "")
        assert payload["custom_details"]["flow"] == flow.name
        link = f"{config.api.url}/{tenant.slug}/flow-run/{flow_run.id}"
        assert msg["links"] == [{"href": link, "text": f"Flow Run {flow_run.name}"}]
