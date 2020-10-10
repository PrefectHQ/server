import uuid

import pytest

from prefect import api, models


class TestSetFlowGroupDefaultParameter:
    async def test_set_flow_group_default_parameter(self, flow_group_id):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first(
            {"default_parameters"}
        )
        assert flow_group.default_parameters == {}

        success = await api.flow_groups.set_flow_group_default_parameters(
            flow_group_id=flow_group_id, parameters={"meep": "morp", "bleep": "blorp"}
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first(
            {"default_parameters"}
        )
        assert flow_group.default_parameters == {"meep": "morp", "bleep": "blorp"}

    async def test_set_flow_group_default_parameter_overwrites_existing(
        self, flow_group_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(default_parameters=dict(x=1))
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first(
            {"default_parameters"}
        )
        assert flow_group.default_parameters == {"x": 1}
        success = await api.flow_groups.set_flow_group_default_parameters(
            flow_group_id=flow_group_id, parameters={}
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first(
            {"default_parameters"}
        )
        assert flow_group.default_parameters == {}

    async def test_set_default_parameter_for_none_flow_group(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.set_flow_group_default_parameters(
                flow_group_id=None, parameters={"meep": "morp"}
            )


class TestSetFlowGroupLabels:
    async def test_set_flow_group_labels(self, flow_group_id):
        labels = ["meep", "morp"]
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels is None

        success = await api.flow_groups.set_flow_group_labels(
            flow_group_id=flow_group_id, labels=labels
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert set(flow_group.labels) == set(labels)

    async def test_set_flow_group_labels_dedupes(self, flow_group_id):
        labels = ["meep", "morp", "morp"]
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels is None

        success = await api.flow_groups.set_flow_group_labels(
            flow_group_id=flow_group_id, labels=labels
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert len(flow_group.labels) == 2
        assert set(flow_group.labels) == {"meep", "morp"}

    @pytest.mark.parametrize("labels", [None, []])
    async def test_set_flow_group_labels_to_none_and_empty_preseves_type(
        self, flow_group_id, labels
    ):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels is None

        success = await api.flow_groups.set_flow_group_labels(
            flow_group_id=flow_group_id, labels=labels
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels == labels

    async def test_set_flow_group_labels_overwrites_existing(self, flow_group_id):
        labels = ["meep", "morp"]
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(labels=["zaphod", "beeblebrox"])
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert set(flow_group.labels) == set(["zaphod", "beeblebrox"])

        await api.flow_groups.set_flow_group_labels(
            flow_group_id=flow_group_id, labels=labels
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert set(flow_group.labels) == set(labels)

    async def test_set_flow_group_labels_for_invalid_flow_group(self):
        success = await api.flow_groups.set_flow_group_labels(
            flow_group_id=str(uuid.uuid4()), labels=["meep", "morp"]
        )
        assert success is False

    async def test_set_flow_group_labels_for_none_flow_group(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.set_flow_group_labels(
                flow_group_id=None, labels=["meep", "morp"]
            )


class TestSetFlowGroupSchedule:
    @pytest.mark.parametrize(
        "clock",
        [
            {"type": "CronClock", "cron": "42 0 0 * * *"},
            {"type": "IntervalClock", "interval": 420000000},
        ],
    )
    async def test_set_flow_group_schedule(self, flow_group_id, clock):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

        success = await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=[clock]
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule["clocks"][0] == clock

    async def test_setting_schedule_deletes_runs(self, flow_id, flow_group_id):
        """
        This test takes a flow with a schedule and ensures that updating the Flow Group
        schedule deletes previously auto-scheduled runs.
        """
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

        # make sure we're starting from a clean slate
        await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).delete()
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0
        await api.flows.set_schedule_active(flow_id=flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10
        # create one manual run that won't be deleted
        await api.runs.create_flow_run(flow_id=flow_id)

        # 10 autoscheduled runs and 1 manual run
        runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert len(runs) == 11
        start_times = {r.scheduled_start_time for r in runs}

        # update the flow group schedule and confirm the runs have been repopulated
        clock = {"type": "CronClock", "cron": "42 0 0 * * *"}

        success = await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=[clock]
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule["clocks"][0] == clock

        # the only run that should still be scheduled from before is the manually created one
        new_runs = await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).get(
            {"scheduled_start_time"}
        )
        assert len({r.scheduled_start_time for r in new_runs} & start_times) == 1

    async def test_set_schedule_with_two_clocks(self, flow_group_id):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

        clocks = [
            {"type": "CronClock", "cron": "42 0 0 * * *"},
            {"type": "CronClock", "cron": "43 0 0 * * *"},
        ]
        success = await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=clocks
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule["clocks"] == [
            {"type": "CronClock", "cron": "42 0 0 * * *"},
            {"type": "CronClock", "cron": "43 0 0 * * *"},
        ]

    @pytest.mark.parametrize(
        "clock",
        [
            {
                "type": "CronClock",
                "cron": "42 0 0 * * *",
                "parameter_defaults": {"meep": "morp"},
            },
            {
                "type": "IntervalClock",
                "interval": 420000000,
                "parameter_defaults": {"meep": "morp"},
            },
        ],
    )
    async def test_set_schedule_with_default_parameters(self, flow_group_id, clock):
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

        clock = {
            "type": "CronClock",
            "cron": "42 0 0 * * *",
            "parameter_defaults": {"foo": "bar"},
        }
        success = await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=[clock]
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule["clocks"][0] == clock

    async def test_set_schedule_overwrites_existing(self, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(schedule=dict(foo="bar"))
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {"foo": "bar"}

        clock = {"type": "CronClock", "cron": "42 0 0 * * *"}
        await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=[clock]
        )

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule["clocks"][0] == clock

    async def test_set_schedule_raises_for_invalid_clock(self, flow_group_id):
        with pytest.raises(ValueError, match="Invalid clock provided for schedule"):
            clock = {"type": "CronClock", "props": {"cron": "xyz"}}
            await api.flow_groups.set_flow_group_schedule(
                flow_group_id=flow_group_id, clocks=[clock]
            )

    async def test_set_schedule_for_none_flow_group(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.set_flow_group_schedule(
                flow_group_id=None,
                clocks=[{"type": "CronClock", "cron": "42 0 0 * * *"}],
            )


class TestDeleteFlowGroupSchedule:
    async def test_delete_flow_group_schedule(self, flow_id, flow_group_id):

        # update the flow group schedule and confirm the runs have been repopulated
        clock = {"type": "CronClock", "cron": "42 0 0 * * *"}

        success = await api.flow_groups.set_flow_group_schedule(
            flow_group_id=flow_group_id, clocks=[clock]
        )
        assert success is True

        await api.flows.set_schedule_active(flow_id=flow_id)
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 10

        success = await api.flow_groups.delete_flow_group_schedule(
            flow_group_id=flow_group_id
        )
        assert success is True

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

        # ensure old runs were deleted
        assert await models.FlowRun.where({"flow_id": {"_eq": flow_id}}).count() == 0

    async def test_delete_flow_group_schedule_for_invalid_flow_group(self):
        success = await api.flow_groups.delete_flow_group_schedule(
            flow_group_id=str(uuid.uuid4())
        )
        assert success is False

    async def test_delete_flow_group_schedule_for_none_flow_group(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.delete_flow_group_schedule(flow_group_id=None)


class TestUpdateFlowHeartbeat:
    async def test_disable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flow_groups.disable_heartbeat(flow_group_id=flow_group_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is False
        assert flow_group.settings["disable_heartbeat"] is True

    async def test_enable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flow_groups.enable_heartbeat(flow_group_id=flow_group_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is True
        assert flow_group.settings["disable_heartbeat"] is False

    async def test_disable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.disable_heartbeat(flow_group_id=None)

    async def test_enable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.enable_heartbeat(flow_group_id=None)


class TestUpdateLazarusForFlow:
    async def test_disable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", False) is True
        assert await api.flow_groups.disable_lazarus(flow_group_id=flow_group_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": False}

    async def test_enable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": False}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", True) is False
        assert await api.flow_groups.enable_lazarus(flow_group_id=flow_group_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": True}

    async def test_disable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.disable_lazarus(flow_group_id=None)

    async def test_enable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.enable_lazarus(flow_group_id=None)
