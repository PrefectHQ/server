"""
Tests that when a state is inserted into the state table, it updates the
associated run's details via Postgres trigger
"""
import pendulum
import pytest

from prefect import models


class TestFlowRunStateTrigger:
    @pytest.mark.parametrize("original_version", [-1, 0, 9, 10])
    async def test_trigger_updates_run_when_state_version_is_greater_or_equal(
        self, tenant_id, flow_run_id, original_version
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": original_version})
        old_run = await models.FlowRun.where(id=flow_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first({"version"})

        assert new_run.version == 10

    async def test_trigger_updates_highest_version_when_multiple_states_inserted(
        self, tenant_id, flow_run_id
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": 10})
        old_run = await models.FlowRun.where(id=flow_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.FlowRunState().insert_many(
            [
                dict(
                    tenant_id=tenant_id,
                    flow_run_id=flow_run_id,
                    version=v,
                    timestamp=dt.add(seconds=v),
                    start_time=dt.add(seconds=v),
                    message="x",
                    result="y",
                    state="z",
                    serialized_state={"a": "b"},
                )
                for v in [1, 5, 10, 11, 12, 100]
            ]
        )

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "state_timestamp"}
        )

        assert new_run.version == 100 != old_run.version
        assert new_run.state_timestamp == dt.add(seconds=100)

    @pytest.mark.parametrize("original_version", [11, 100])
    async def test_trigger_does_not_update_run_when_when_state_version_is_lower(
        self, tenant_id, flow_run_id, original_version
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": original_version})

        old_run = await models.FlowRun.where(id=flow_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first({"version"})

        assert new_run.version == old_run.version

    async def test_trigger_updates_start_time_if_running(self, tenant_id, flow_run_id):

        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time == dt
        assert new_run.end_time is None

    async def test_trigger_does_not_update_start_time_if_greater_than_current(
        self, tenant_id, flow_run_id
    ):

        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt.subtract(minutes=10),
            start_time=dt,
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=11,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time == dt.subtract(minutes=10)
        assert new_run.end_time is None

    @pytest.mark.parametrize(
        "state", ["Success", "Failed", "Cached", "TimedOut", "Looped", "Cancelled"]
    )
    async def test_trigger_updates_end_time_if_finished(
        self, tenant_id, flow_run_id, state
    ):

        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time is None
        assert new_run.end_time == dt

    @pytest.mark.parametrize(
        "state", ["Success", "Failed", "Cached", "TimedOut", "Looped", "Cancelled"]
    )
    async def test_trigger_does_not_update_end_time_if_less_than_current(
        self, tenant_id, flow_run_id, state
    ):

        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt.add(minutes=10),
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()
        await models.FlowRunState(
            tenant_id=tenant_id,
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time is None
        assert new_run.end_time == dt.add(minutes=10)


class TestTaskRunStateTrigger:
    @pytest.mark.parametrize("original_version", [-1, 0, 9, 10])
    async def test_trigger_updates_run_when_state_version_is_greater_or_equal(
        self, tenant_id, task_run_id, original_version
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": original_version})
        old_run = await models.TaskRun.where(id=task_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first({"version"})

        assert new_run.version == 10

    async def test_trigger_updates_highest_version_when_multiple_states_inserted(
        self, tenant_id, task_run_id
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": 10})
        old_run = await models.TaskRun.where(id=task_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.TaskRunState().insert_many(
            [
                dict(
                    tenant_id=tenant_id,
                    task_run_id=task_run_id,
                    version=v,
                    timestamp=dt.add(seconds=v),
                    start_time=dt.add(seconds=v),
                    message="x",
                    result="y",
                    state="z",
                    serialized_state={"a": "b"},
                )
                for v in [1, 5, 10, 11, 12, 100]
            ]
        )

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state_timestamp"}
        )

        assert new_run.version == 100 != old_run.version
        assert new_run.state_timestamp == dt.add(seconds=100)

    @pytest.mark.parametrize("original_version", [11, 100])
    async def test_trigger_does_not_update_run_when_when_state_version_is_lower(
        self, tenant_id, task_run_id, original_version
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": original_version})

        old_run = await models.TaskRun.where(id=task_run_id).first({"version"})

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first({"version"})

        assert new_run.version == old_run.version

    async def test_trigger_updates_start_time_if_running(self, tenant_id, task_run_id):

        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time == dt
        assert new_run.end_time is None

    async def test_trigger_does_not_update_start_time_if_greater_than_current(
        self, tenant_id, task_run_id
    ):

        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt.subtract(minutes=10),
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=11,
            timestamp=dt,
            message="x",
            result="y",
            state="Running",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time == dt.subtract(minutes=10)
        assert new_run.end_time is None

    @pytest.mark.parametrize(
        "state", ["Success", "Failed", "Cached", "TimedOut", "Looped", "Cancelled"]
    )
    async def test_trigger_updates_end_time_if_finished(
        self, tenant_id, task_run_id, state
    ):

        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time is None
        assert new_run.end_time == dt

    @pytest.mark.parametrize(
        "state", ["Success", "Failed", "Cached", "TimedOut", "Looped", "Cancelled"]
    )
    async def test_trigger_does_not_update_end_time_if_less_than_current(
        self, tenant_id, task_run_id, state
    ):

        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert old_run.start_time is None
        assert old_run.end_time is None

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=10,
            timestamp=dt.add(minutes=10),
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()
        await models.TaskRunState(
            tenant_id=tenant_id,
            task_run_id=task_run_id,
            version=11,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state=state,
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time"}
        )
        assert new_run.start_time is None
        assert new_run.end_time == dt.add(minutes=10)
