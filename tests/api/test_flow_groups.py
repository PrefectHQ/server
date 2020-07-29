import uuid

import pytest

from prefect_server import api
from prefect_server.database import models


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
        assert flow_group.labels == labels

    async def test_set_flow_group_labels_overwrites_existing(self, flow_group_id):
        labels = ["meep", "morp"]
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(labels=["zaphod", "beeblebrox"])
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels == ["zaphod", "beeblebrox"]

        await api.flow_groups.set_flow_group_labels(
            flow_group_id=flow_group_id, labels=labels
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels == labels

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
    async def test_delete_flow_group_schedule(self, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(schedule={"foo": "bar"})
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {"foo": "bar"}

        success = await api.flow_groups.delete_flow_group_schedule(
            flow_group_id=flow_group_id
        )
        assert success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None

    async def test_delete_flow_group_schedule_for_invalid_flow_group(self):
        success = await api.flow_groups.delete_flow_group_schedule(
            flow_group_id=str(uuid.uuid4())
        )
        assert success is False

    async def test_delete_flow_group_schedule_for_none_flow_group(self):
        with pytest.raises(ValueError, match="Invalid flow group ID"):
            await api.flow_groups.delete_flow_group_schedule(flow_group_id=None)
