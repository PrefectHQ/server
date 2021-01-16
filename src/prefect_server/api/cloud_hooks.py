import asyncio
import json
import uuid
from typing import List

import httpx
from box import Box

import prefect
from prefect import api, models
from prefect.utilities.plugins import register_api
from prefect_server import config as server_config
from prefect_server.utilities import events, logging, names

cloud_hook_httpx_client = httpx.AsyncClient()

logger = logging.get_logger("cloud_hooks")
CLOUD_HOOK_TYPES = {
    "WEBHOOK",
    "SLACK_WEBHOOK",
    "PREFECT_MESSAGE",
    "TWILIO",
    "PAGERDUTY",
}

ALL_STATES = [s.__name__.upper() for s in prefect.engine.state.State.children()]


@register_api("cloud_hooks.create_cloud_hook")
async def create_cloud_hook(
    tenant_id: str,
    type: str,
    states: List[str],
    config: dict = None,
    version_group_id: str = None,
    name=None,
) -> str:
    """
    Creates a cloud hook that responds to changes in flow run states.

    Args:
        - tenant_id (str): the tenant ID
        - type (str): the cloud hook type
        - states (List[str]): a list of states to monitor
        - config (str): the URL to which the webhook payload will be posted
        - version_group_id (str): the version group ID to monitor; if None, all flows
            from all version groups will trigger the webhook
        - name (str): an optional name for the hook

    Returns:
        - str: the webhook ID

    Raises:
        - ValueError: if the tenant id is None
        - ValueError: if the type is invalid
        - ValueError: if any state is invalid
    """
    if not tenant_id:
        raise ValueError("Invalid tenant ID")

    if not states:
        raise ValueError("Invalid states")

    states = list({s.upper() for s in states})
    if not all(s in ALL_STATES for s in states):
        raise ValueError("Invalid states")

    if type not in CLOUD_HOOK_TYPES:
        raise ValueError("Invalid cloud hook type")
    elif type == "WEBHOOK":
        if set(config or {}) != {"url"}:
            raise ValueError("Invalid config; expected `url`")
    elif type == "SLACK_WEBHOOK":
        if set(config or {}) != {"url"}:
            raise ValueError("Invalid config; expected `url`")
    elif type == "TWILIO":
        if (
            set(config or {})
            != {
                "account_sid",
                "auth_token",
                "messaging_service_sid",
                "to",
            }
            or not config.get("to")
        ):
            raise ValueError(
                "Invalid config; expected `account_sid`, `auth_token`, `messaging_service_sid`, and `to`"
            )
    elif type == "PAGERDUTY":
        if set(config or {}) != {
            "api_token",
            "routing_key",
            "severity",
        }:
            raise ValueError(
                "Invalid config; expected `api_token`, `routing_key`, & `severity`"
            )
        if config["severity"] not in {"info", "warning", "error", "critical"}:
            raise ValueError(
                "Invalid config; severity must be one of {info, warning, error, critical}"
            )
    return await models.CloudHook(
        tenant_id=tenant_id,
        version_group_id=version_group_id,
        config=config,
        type=type,
        states=states,
        active=True,
        name=name,
    ).insert()


@register_api("cloud_hooks.delete_cloud_hook")
async def delete_cloud_hook(cloud_hook_id: str) -> bool:
    """
    Deletes a cloud hook

    Args:
        - cloud_hook_id (str): the cloud hook ID

    Returns:
        bool: if the delete succeeded
    """

    if cloud_hook_id is None:
        raise ValueError("Invalid ID")

    result = await models.CloudHook.where(id=cloud_hook_id).delete()
    return bool(result.affected_rows)


@register_api("cloud_hooks.set_cloud_hook_active")
async def set_cloud_hook_active(cloud_hook_id: str) -> bool:
    """
    Activates a cloud hook.

    Args:
        - cloud_hook_id (str): the cloud hook ID

    Returns:
        bool: if the update succeeded
    """
    if cloud_hook_id is None:
        raise ValueError("Invalid ID")

    result = await models.CloudHook.where(id=cloud_hook_id).update(set={"active": True})

    return bool(result.affected_rows)


@register_api("cloud_hooks.set_cloud_hook_inactive")
async def set_cloud_hook_inactive(cloud_hook_id: str) -> bool:
    """
    Toggles a cloud hook's active value: if active, makes it inactive; and vice versa.

    Args:
        - cloud_hook_id (str): the cloud hook ID

    Returns:
        bool: if the update succeeded
    """
    if cloud_hook_id is None:
        raise ValueError("Invalid ID")

    result = await models.CloudHook.where(id=cloud_hook_id).update(
        set={"active": False}
    )
    return bool(result.affected_rows)


@register_api("cloud_hooks.call_hooks")
async def call_hooks(event: events.FlowRunStateChange):
    """
    Calls flow run cloud hooks when passed an Event representing a flow run state change.
    """

    async def log_errors(coro):
        """
        Helper function for trapping and logging errors in a coroutine

        async def bad_fn():
            1/0

        await log_errors(bad_fn()) # logs error
        """
        try:
            await coro
        except Exception as exc:
            logger.error(exc)

    tasks = []
    for hook in await _get_matching_hooks(event=event):
        if hook.type == "WEBHOOK":
            tasks.append(_call_webhook(url=hook.config["url"], event=event))
        if hook.type == "SLACK_WEBHOOK":
            tasks.append(_call_slack_webhook(url=hook.config["url"], event=event))
        if hook.type == "TWILIO":
            tasks.append(
                _call_twilio(
                    account_sid=hook.config["account_sid"],
                    auth_token=hook.config["auth_token"],
                    messaging_service_sid=hook.config["messaging_service_sid"],
                    to=hook.config["to"],
                    event=event,
                )
            )
        if hook.type == "PAGERDUTY":
            tasks.append(
                _call_pagerduty(
                    api_token=hook.config["api_token"],
                    routing_key=hook.config["routing_key"],
                    severity=hook.config["severity"],
                    event=event,
                )
            )
        if hook.type == "PREFECT_MESSAGE":
            tasks.append(_call_prefect_message(event=event))

    # return exceptions so that any error doesn't cancel the other hooks
    await asyncio.gather(*[log_errors(t) for t in tasks], return_exceptions=True)


@register_api("cloud_hooks._get_matching_hooks")
async def _get_matching_hooks(event: events.FlowRunStateChange) -> List[Box]:
    """
    Retrieves cloud hooks that match either the flow or states of the supplied event.
    """
    state = event.state.state.upper()

    hooks = await models.CloudHook.where(
        {
            "tenant_id": {"_eq": event.tenant.id},
            # the hook is active
            "active": {"_eq": True},
            # the hook matches the provided state
            "states": {"_has_keys_any": event.state.state.upper()},
            # the hook either matches this version group id or all flows from all
            # version group IDs
            "_or": [
                {"version_group_id": {"_eq": event.flow.version_group_id}},
                {"version_group_id": {"_is_null": True}},
            ],
        },
    ).get({"id", "type", "config"})

    return hooks


async def _call_webhook(url: str, event: events.FlowRunStateChange):
    await cloud_hook_httpx_client.post(
        url,
        json=dict(event=json.loads(event.json())),
        headers={"X-PREFECT-EVENT-ID": event.id},
        timeout=2,
    )


async def _call_slack_webhook(url: str, event: events.FlowRunStateChange):
    message_link = (
        f"{server_config.api.url}/{event.tenant.slug}/flow-run/{event.flow_run.id}"
    )
    slack_message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Run `{event.flow_run.name}` of flow `{event.flow.name}` entered a new state:",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*State:* `{event.state.state}`"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:* {event.state.serialized_state['message']}",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Link:* {message_link}"},
            },
        ]
    }

    result = await cloud_hook_httpx_client.post(url, json=slack_message, timeout=1)


async def _call_twilio(
    account_sid: str,
    auth_token: str,
    messaging_service_sid: str,
    to: List[str],
    event: events.FlowRunStateChange,
):

    message_text = f"Run {event.flow_run.name} of flow {event.flow.name} entered a new state: {event.state.state}. \n Link: "
    message_link = (
        f"{server_config.api.url}/{event.tenant.slug}/flow-run/{event.flow_run.id}"
    )

    # send messages for each number in the to list
    for phone_number in to:
        result = await cloud_hook_httpx_client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data={
                "To": phone_number,
                "From": messaging_service_sid,
                "Body": f"{message_text}{message_link}",
            },
            auth=(account_sid, auth_token),
            timeout=2,
        )


async def _call_pagerduty(
    api_token: str, routing_key: str, severity: str, event: events.FlowRunStateChange
):

    tenant_slug = event.tenant.slug
    state = event.state.state
    state_message = event.state.serialized_state["message"] or ""
    flow_run = event.flow_run.name
    flow_name = event.flow.name
    link = f"{server_config.api.url}/{tenant_slug}/flow-run/{event.flow_run.id}"

    msg = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": f"Run {flow_run} entered a new state: {state}",
            "severity": severity,
            "source": f"cloud.prefect.io/{tenant_slug}",
            "component": flow_name,
            "group": flow_run,
            "class": f"State->{state}",
            "custom_details": {
                "flow": flow_name,
                "flow_run": flow_run,
                "state": state,
                "state_message": state_message,
                "tenant_slug": tenant_slug,
            },
        },
        "links": [{"href": link, "text": f"Flow Run {flow_run}"}],
    }

    await cloud_hook_httpx_client.post(
        "https://events.pagerduty.com/v2/enqueue",
        json=msg,
        headers={"Authorization": f"Token token={api_token}"},
        timeout=2,
    )


async def _call_prefect_message(event: events.FlowRunStateChange):
    tenant_id = event.tenant.id
    if not tenant_id:
        raise ValueError("Invalid tenant ID.")

    await api.messages.create_message(
        tenant_id=event.tenant.id,
        type="CLOUD_HOOK",
        content=dict(event=event, type="CLOUD_HOOK"),
    )


@register_api("cloud_hooks.test_cloud_hook")
async def test_cloud_hook(
    cloud_hook_id: str,
    flow_run_id: str = None,
    state: prefect.engine.state.State = None,
):
    """
    Sends a test payload to a hook

    Args:
        - cloud_hook_id (str): the hook id
        - flow_run_id (str, optional): a flow run ID to test with. If provided, the event will pull event details
            from the flow run
        - state (State, optional): a sample state
    """

    if state is None:
        state = prefect.engine.state.Success(message="Test success state")
    serialized_state = state.serialize()

    if cloud_hook_id is None:
        raise ValueError("Invalid ID")

    # verify that the hook actually exists
    hook = await models.CloudHook.where(id=cloud_hook_id).first(
        {"type", "config", "tenant_id"}
    )
    if not hook:
        raise ValueError("Invalid ID")

    # if a flow run has been provided, construct an event mirroring the actual event
    # we'd expect to see
    if flow_run_id:
        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"id", "tenant_id", "flow_id", "name", "version"}
        )
        new_flow_run = Box(
            id=flow_run.id,
            is_test_event=True,
            tenant_id=flow_run.tenant_id,
            flow_id=flow_run.flow_id,
            name=flow_run.name,
            version=flow_run.version + 1,
            state=type(state).__name__,
            serialized_state=state.serialize(),
        )
        flow = await models.Flow.where(id=flow_run.flow_id).first(
            selection_set={
                "id": True,
                "tenant_id": True,
                "name": True,
                "environment": True,
                "version_group_id": True,
            }
        )

        tenant = await models.Tenant.where(id=flow_run.tenant_id).first({"id", "slug"})

        test_event = events.FlowRunStateChange(
            flow_run=new_flow_run.to_dict(),
            flow=flow.dict(),
            tenant=tenant.dict(),
            state=dict(
                version=1,
                state=serialized_state["type"],
                serialized_state=serialized_state,
            ),
        )
    # otherwise populate the event with dummy data
    else:
        test_event = events.FlowRunStateChange(
            is_test_event=True,
            flow_run=dict(id=str(uuid.uuid4()), name=names.generate_slug(2)),
            tenant=dict(id=hook.tenant_id, slug="test-slug"),
            flow=dict(id=str(uuid.uuid4()), name="Cloud Hook Test Flow"),
            state=dict(
                version=1,
                state=serialized_state["type"],
                serialized_state=serialized_state,
            ),
        )

    if hook.type == "WEBHOOK":
        await _call_webhook(url=hook.config["url"], event=test_event)
    elif hook.type == "SLACK_WEBHOOK":
        await _call_slack_webhook(url=hook.config["url"], event=test_event)
    elif hook.type == "PREFECT_MESSAGE":
        await _call_prefect_message(event=test_event)
    elif hook.type == "TWILIO":
        await _call_twilio(
            account_sid=hook.config["account_sid"],
            auth_token=hook.config["auth_token"],
            messaging_service_sid=hook.config["messaging_service_sid"],
            to=hook.config["to"],
            event=test_event,
        )
    elif hook.type == "PAGERDUTY":
        await _call_pagerduty(
            api_token=hook.config["api_token"],
            routing_key=hook.config["routing_key"],
            severity=hook.config["severity"],
            event=test_event,
        )
    else:
        raise ValueError("Invalid type")
