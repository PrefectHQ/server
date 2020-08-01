import pendulum
import pytest

import prefect
from prefect.engine.state import Retrying, Scheduled
from prefect import api
from prefect_server.database import models
from prefect_server.services.towel.zombie_killer import ZombieKiller


@pytest.fixture(autouse=True)
async def delete_other_flow_runs(running_flow_run_id):
    # delete any flow runs other than the pytest fixture to ensure a controlled environment
    await models.FlowRun.where({"id": {"_neq": running_flow_run_id}}).delete()


async def test_zombie_killer_fails_task_run(running_flow_run_id, task_run_id):
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await ZombieKiller().run_once() == 1

    task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
    flow_run = await models.FlowRun.where(id=running_flow_run_id).first({"state"})
    assert task_run.state == "Failed"
    assert flow_run.state == "Running"


async def test_zombie_killer_does_not_fail_dead_flow_run_if_task_still_heartbeating(
    running_flow_run_id, task_run_id
):
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat on flow run, but recent one on task run
    await models.FlowRun.where(id=running_flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(seconds=1)}
    )

    assert await ZombieKiller().run_once() == 0

    task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
    flow_run = await models.FlowRun.where(id=running_flow_run_id).first({"state"})
    assert task_run.state == "Running"
    assert flow_run.state == "Running"


async def test_zombie_killer_does_not_fail_flow_run_if_heartbeat_disabled(
    flow_id, flow_group_id, running_flow_run_id, task_run_id
):

    # mark heartbeat_enabled as False
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(heartbeat_enabled=False))
    )
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat on flow run and task run
    await models.FlowRun.where(id=running_flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await ZombieKiller().run_once() == 0


async def test_zombie_killer_fails_flow_run_if_heartbeat_setting_set_but_not_disabled(
    flow_id, flow_group_id, running_flow_run_id, task_run_id
):

    # mark heartbeat_enabled as True
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(heartbeat_enabled=True))
    )
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat on flow run and task run
    await models.FlowRun.where(id=running_flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await ZombieKiller().run_once() == 1
    task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
    assert task_run.state == "Failed"


async def test_zombie_killer_fails_flow_run_if_heartbeat_setting_not_set(
    flow_id, flow_group_id, running_flow_run_id, task_run_id
):
    await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
    flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

    assert not "disable_heartbeat" in flow_group.settings
    assert not "heartbeat_disabled" in flow_group.settings

    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat on flow run and task run
    await models.FlowRun.where(id=running_flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await ZombieKiller().run_once() == 1
    task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
    assert task_run.state == "Failed"


@pytest.mark.parametrize(
    "state",
    [
        Scheduled(start_time=pendulum.now("UTC").add(hours=1)),
        Retrying(start_time=pendulum.now("UTC").add(hours=1)),
    ],
)
async def test_zombie_killer_does_not_apply_if_task_run_is_scheduled(
    running_flow_run_id, task_run_id, state
):
    await api.states.set_task_run_state(task_run_id, state=state)

    # set old heartbeats
    await models.FlowRun.where(id=running_flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await ZombieKiller().run_once() == 0


async def test_zombie_killer_does_not_apply_if_heartbeat_is_recent(
    running_flow_run_id, task_run_id
):
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    assert await ZombieKiller().run_once() == 0

    task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
    assert task_run.state == "Running"
    flow_run = await models.FlowRun.where(id=running_flow_run_id).first({"state"})
    assert flow_run.state == "Running"


async def test_zombie_killer_creates_logs(running_flow_run_id, task_run_id):
    await api.states.set_task_run_state(
        task_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat
    await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    t_where = {
        "flow_run_id": {"_eq": running_flow_run_id},
        "task_run_id": {"_eq": task_run_id},
    }

    t_log_count = await models.Log.where(t_where).count()
    assert await ZombieKiller().run_once() == 1
    assert await models.Log.where(t_where).count() == t_log_count + 1

    t_log = await models.Log.where(t_where).first(
        selection_set={"message", "level", "name"}
    )
    assert "No heartbeat detected from the remote task" in t_log.message
    assert t_log.level == "ERROR"
    assert t_log.name == "prefect-server.ZombieKiller.TaskRun"


class TestZombieKillerRetries:
    async def test_zombie_killer_retries_if_max_retries_greater_than_0(
        running_flow_run_id, task_id, task_run_id
    ):

        await models.Task.where(id=task_id).update(
            {"max_retries": 1, "retry_delay": "00:00:00"}
        )

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        # set old heartbeat
        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"state", "state_start_time"}
        )
        assert task_run.state == "Retrying"
        assert task_run.state_start_time < pendulum.now()

    async def test_zombie_killer_retries_if_retry_delay_missing(
        running_flow_run_id, task_id, task_run_id
    ):

        await models.Task.where(id=task_id).update(
            {"max_retries": 1, "retry_delay": None}
        )

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        # set old heartbeat
        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"state", "state_start_time"}
        )
        assert task_run.state == "Retrying"
        assert task_run.state_start_time < pendulum.now()

    async def test_zombie_killer_respects_retry_delay(
        running_flow_run_id, task_id, task_run_id
    ):

        await models.Task.where(id=task_id).update(
            {"max_retries": 1, "retry_delay": "01:00:00"}
        )

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        # set old heartbeat
        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"state", "state_start_time"}
        )
        assert task_run.state == "Retrying"
        assert (
            pendulum.now().add(hours=1, minutes=-1)
            < task_run.state_start_time
            < pendulum.now().add(hours=1)
        )

    async def test_zombie_killer_respects_retry_delay_in_postgres_readable_syntax(
        running_flow_run_id, task_id, task_run_id
    ):

        await models.Task.where(id=task_id).update(
            {"max_retries": 1, "retry_delay": "17 days 01:00:03"}
        )

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        # set old heartbeat
        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"state", "state_start_time"}
        )
        assert task_run.state == "Retrying"
        assert (
            pendulum.now().add(days=17, hours=1, seconds=2)
            < task_run.state_start_time
            < pendulum.now().add(days=17, hours=1, seconds=3)
        )

    async def test_zombie_killer_stops_retrying_if_max_retries_exceeded(
        running_flow_run_id, task_id, task_run_id
    ):

        await models.Task.where(id=task_id).update(
            {"max_retries": 1, "retry_delay": "00:00:00"}
        )

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        # set old heartbeat
        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
        assert task_run.state == "Retrying"

        # put back in running state and kill

        await api.states.set_task_run_state(
            task_run_id, state=prefect.engine.state.Running()
        )

        await models.TaskRun.where(id=task_run_id).update(
            set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
        )

        assert await ZombieKiller().run_once() == 1

        task_run = await models.TaskRun.where(id=task_run_id).first({"state"})
        assert task_run.state == "Failed"
