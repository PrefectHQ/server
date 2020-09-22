import pytest

from prefect import api
from prefect import models as m
from prefect_server.services.towel.scheduler import Scheduler


@pytest.fixture(autouse=True)
async def clear_scheduled_runs(flow_id):
    await m.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()


async def test_scheduler_creates_runs():
    assert await Scheduler().run_once() == 10


async def test_scheduler_creates_no_runs_if_run_twice_quickly():
    assert await Scheduler().run_once() == 10
    assert await Scheduler().run_once() == 0


async def test_scheduler_does_not_run_for_archived_flows(flow_id):
    await api.flows.archive_flow(flow_id=flow_id)
    assert await Scheduler().run_once() == 0


async def test_scheduler_does_not_run_for_flows_with_inactive_schedules(flow_id):
    await api.flows.set_schedule_inactive(flow_id=flow_id)
    assert await Scheduler().run_once() == 0
