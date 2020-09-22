import pendulum
import pytest

import prefect
from prefect import api, models
from prefect_server import config
from prefect_server.services.towel.lazarus import Lazarus


@pytest.fixture(autouse=True)
async def delete_other_flow_runs(flow_run_id):
    # delete any flow runs other than the pytest fixture to ensure a controlled environment
    await models.FlowRun.where({"id": {"_neq": flow_run_id}}).delete()


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_restarts_flow_run(flow_run_id, state):
    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 1

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"state", "times_resurrected"}
    )
    assert flow_run.times_resurrected == 1
    assert flow_run.state == "Scheduled"


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_does_not_restart_flow_run_if_lazarus_disabled(
    flow_id, flow_run_id, flow_group_id, state
):
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(lazarus_enabled=False))
    )

    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 0

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"state", "times_resurrected"}
    )
    assert flow_run.times_resurrected == 0
    assert flow_run.state == state.serialize()["type"]


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_does_not_restart_flow_run_if_heartbeat_disabled(
    flow_id, flow_group_id, flow_run_id, state
):
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(heartbeat_enabled=False))
    )
    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 0

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"state", "times_resurrected"}
    )
    assert flow_run.times_resurrected == 0
    assert flow_run.state == state.serialize()["type"]


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_does_not_restart_flow_run_if_lazarus_and_heartbeat_disabled(
    flow_id, flow_group_id, flow_run_id, state
):
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(lazarus_enabled=False, heartbeat_enabled=False))
    )
    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 0

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"state", "times_resurrected"}
    )
    assert flow_run.times_resurrected == 0
    assert flow_run.state == state.serialize()["type"]


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_restarts_flow_run_if_lazarus_setting_set_but_not_disabled(
    flow_id, flow_group_id, flow_run_id, state
):
    await models.FlowGroup.where(id=flow_group_id).update(
        set=dict(settings=dict(lazarus_enabled=True))
    )
    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 1

    flow_run = await models.FlowRun.where(id=flow_run_id).first(
        {"state", "times_resurrected"}
    )
    assert flow_run.times_resurrected == 1
    assert flow_run.state == "Scheduled"


async def test_lazarus_creates_flow_run_log(flow_run_id):
    # update run state
    await api.states.set_flow_run_state(
        flow_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    f_where = {"flow_run_id": {"_eq": flow_run_id}}

    log_count = await models.Log.where(f_where).count()
    assert await Lazarus().run_once() == 1

    assert await models.Log.where(f_where).count() == log_count + 1
    log = await models.Log.where(f_where).first(
        selection_set={"message", "level", "name"}
    )
    assert log.message == "Rescheduled by a Lazarus process. This is attempt 1."
    assert log.level == "INFO"
    assert log.name == "prefect-server.Lazarus.FlowRun"


@pytest.mark.parametrize(
    "state",
    [
        prefect.engine.state.Failed(),
        prefect.engine.state.Success(),
        prefect.engine.state.Pending(),
        prefect.engine.state.Scheduled(),
    ],
)
async def test_lazarus_doesnt_restart_flow_run_that_isnt_running(flow_run_id, state):
    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 0

    flow_run = await models.FlowRun.where(id=flow_run_id).first({"state"})
    assert flow_run.state == type(state).__name__


@pytest.mark.parametrize(
    "task_state",
    [
        prefect.engine.state.Running(),
        prefect.engine.state.Retrying(),
        prefect.engine.state.Resume(),
        prefect.engine.state.Paused(),
        prefect.engine.state.Scheduled(),
    ],
)
async def test_lazarus_doesnt_restart_flow_run_with_active_tasks(
    flow_run_id, task_run_id, task_state
):
    # update run state
    await api.states.set_flow_run_state(
        flow_run_id, state=prefect.engine.state.Running()
    )
    # set task state
    await api.states.set_task_run_state(task_run_id, state=task_state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    assert await Lazarus().run_once() == 0
    flow_run = await models.FlowRun.where(id=flow_run_id).first({"version"})
    assert flow_run.version == 3


async def test_lazarus_doesnt_restart_flow_run_with_recent_heartbeat(flow_run_id):
    # update run state
    await api.states.set_flow_run_state(
        flow_run_id, state=prefect.engine.state.Running()
    )

    assert await Lazarus().run_once() == 0


@pytest.mark.parametrize(
    "state", [prefect.engine.state.Running(), prefect.engine.state.Submitted()]
)
async def test_lazarus_doesnt_restart_flow_run_if_exceeding_times_attempted_limit(
    flow_run_id, state
):
    # set times_resurrected at the limit
    await models.FlowRun.where(id=flow_run_id).update(
        set=dict(times_resurrected=config.services.lazarus.resurrection_attempt_limit)
    )

    # update run state
    await api.states.set_flow_run_state(flow_run_id, state=state)

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    await models.FlowRun.where(id=flow_run_id).first({"state"})
    assert await Lazarus().run_once() == 0
    dead_run = await models.FlowRun.where(id=flow_run_id).first({"state"})
    assert dead_run.state == "Failed"


async def test_lazarus_logs_even_if_flow_run_exceeding_times_attempted_limit(
    flow_run_id,
):
    # set times_resurrected at the limit
    await models.FlowRun.where(id=flow_run_id).update(
        set=dict(times_resurrected=config.services.lazarus.resurrection_attempt_limit)
    )

    # update run state
    await api.states.set_flow_run_state(
        flow_run_id, state=prefect.engine.state.Running()
    )

    # set old heartbeat
    await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc").subtract(hours=1)}
    )

    f_where = {"flow_run_id": {"_eq": flow_run_id}}

    log_count = await models.Log.where(f_where).count()
    assert await Lazarus().run_once() == 0

    assert await models.Log.where(f_where).count() == log_count + 1
    log = await models.Log.where(f_where).first(
        selection_set={"message", "level", "name"}
    )
    assert "A Lazarus process attempted to reschedule this run" in log.message
    assert "Marking as failed" in log.message
    assert log.level == "ERROR"
    assert log.name == "prefect-server.Lazarus.FlowRun"
