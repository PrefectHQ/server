import pytest

from prefect import api, models
from prefect.serialization.schedule import ScheduleSchema


class TestSetFlowGroupLabels:
    mutation = """
        mutation($input: set_flow_group_labels_input!) {
            set_flow_group_labels(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_group_labels(self, run_query, flow_group_id):
        labels = ["meep", "morp"]
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_group_id=flow_group_id, labels=labels)),
        )
        assert result.data.set_flow_group_labels.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert set(flow_group.labels) == set(labels)

    @pytest.mark.parametrize("labels", [None, []])
    async def test_set_flow_group_labels_preserves_type(
        self, run_query, flow_group_id, labels
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_group_id=flow_group_id, labels=labels)),
        )
        assert result.data.set_flow_group_labels.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels == labels

    async def test_clear_flow_group_labels(self, run_query, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(labels=["zaphod"])
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels == ["zaphod"]

        await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_group_id=flow_group_id, labels=None)),
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"labels"})
        assert flow_group.labels is None


class TestSetFlowGroupSchedule:
    mutation = """
        mutation($input: set_flow_group_schedule_input!) {
            set_flow_group_schedule(input: $input) {
                success
            }
        }
    """

    async def test_set_cron_clocks_for_flow_group_schedule(
        self, run_query, flow_group_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_group_id=flow_group_id,
                    cron_clocks=[
                        {
                            "cron": "42 0 0 * * *",
                            "parameter_defaults": {"meep": "morp"},
                        },
                        {"cron": "43 0 0 * * *"},
                    ],
                )
            ),
        )
        assert result.data.set_flow_group_schedule.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {
            "type": "Schedule",
            "clocks": [
                {
                    "type": "CronClock",
                    "cron": "42 0 0 * * *",
                    "parameter_defaults": {"meep": "morp"},
                },
                {"type": "CronClock", "cron": "43 0 0 * * *"},
            ],
        }

    async def test_add_interval_clocks_to_flow_group_schedule(
        self, run_query, flow_group_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_group_id=flow_group_id,
                    interval_clocks=[
                        {"interval": 4200, "parameter_defaults": {"meep": "morp"}},
                        {"interval": 4300},
                    ],
                )
            ),
        )
        assert result.data.set_flow_group_schedule.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {
            "type": "Schedule",
            "clocks": [
                {
                    "type": "IntervalClock",
                    "interval": 4200000000,
                    "parameter_defaults": {"meep": "morp"},
                },
                {"type": "IntervalClock", "interval": 4300000000},
            ],
        }

    async def test_add_cron_and_interval_clocks_to_flow_group_schedule(
        self, run_query, flow_group_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_group_id=flow_group_id,
                    cron_clocks=[{"cron": "42 0 0 * * *"}],
                    interval_clocks=[{"interval": 4200}],
                )
            ),
        )
        assert result.data.set_flow_group_schedule.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {
            "type": "Schedule",
            "clocks": [
                {"type": "CronClock", "cron": "42 0 0 * * *"},
                {"type": "IntervalClock", "interval": 4200000000},
            ],
        }

    async def test_interval_clock_units(self, run_query, flow_group_id):
        await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_group_id=flow_group_id,
                    interval_clocks=[{"interval": 60}],
                )
            ),
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        deserialized_schedule = ScheduleSchema().load(flow_group.schedule)
        next_two = deserialized_schedule.next(n=2)
        assert next_two[0].add(minutes=1) == next_two[1]


class TestDeleteFlowGroupSchedule:
    mutation = """
        mutation($input: delete_flow_group_schedule_input!) {
            delete_flow_group_schedule(input: $input) {
                success
            }
        }
    """

    async def test_delete_flow_group_schedule(self, run_query, flow_group_id):

        await models.FlowGroup.where(id=flow_group_id).update(
            set=dict(schedule={"foo": "bar"})
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule == {"foo": "bar"}

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_group_id=flow_group_id)),
        )
        assert result.data.delete_flow_group_schedule.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"schedule"})
        assert flow_group.schedule is None
