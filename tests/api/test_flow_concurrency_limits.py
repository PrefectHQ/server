import asyncio
import uuid
from typing import List

import pytest

import prefect
from prefect.engine.state import Running
from prefect_server import api
from prefect_server.database import models


@pytest.fixture(autouse=True)
async def disable_labeled_version_locking(labeled_flow_id: str):
    # Since we're going to be messing with flow's states that
    # won't be following the normal transition pattern, we're going to
    # disable version locking so we don't need to keep following
    # the version number

    flow = await models.Flow.where(id=labeled_flow_id).first({"flow_group_id"})

    await api.flow_groups.update_setting(
        flow.flow_group_id, key="version_locking_enabled", value=False
    )
    yield


@pytest.fixture
async def set_flow_run_concurrency_limits_to_10(
    flow_concurrency_limit_id: str, flow_concurrency_limit_id_2: str
):
    await models.FlowConcurrencyLimit.where(
        {"id": {"_in": [flow_concurrency_limit_id, flow_concurrency_limit_id_2]}}
    ).update(set={"limit": 10})
    yield


@pytest.fixture
async def labeled_flow_group_id(labeled_flow_id: str) -> str:
    result = await models.Flow.where(id=labeled_flow_id).first({"flow_group_id"})
    return result.flow_group_id


class TestGetAvailableFlowRunConcurrency:
    """
    The fixtures have the following labels & information:
        flow_id -> unlabeled environment
        flow_group_id -> flow group for `flow_id`. Unlabeled by default
        labeled_flow_id -> environment labels ["foo", "bar"]
        labeled_flow_run_id -> a flow run for labeled_flow_id in a running state
        
    To do testing, we're going to fiddle with either the number of
    flow runs for flow `labeled_flow_id`, or add labels to the
    `flow_group_id`'s flow group (associated with `flow_id`, which
    is an unlabeled flow)
    """

    async def set_flow_group_labels(
        self, flow_group_id: str, labels: List[str] = None
    ) -> None:
        labels = labels or ["foo", "bar"]

        flow_group = await models.FlowGroup.where(id=flow_group_id).update(
            set={"labels": labels}
        )

    async def test_counts_duplicated_labels_once(
        self,
        tenant_id: str,
        labeled_flow_id: str,
        labeled_flow_group_id: str,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
        flow_concurrency_limit_2: models.FlowConcurrencyLimit,
        set_flow_run_concurrency_limits_to_10,
    ):
        """
        Tests to make sure that if a label exists on both
        a flow group and a flow's environment for the same flow,
        it is only counted once towards the concurrency slot
        """

        await asyncio.gather(
            *[
                self.set_flow_group_labels(labeled_flow_group_id),
                api.states.set_flow_run_state(labeled_flow_run_id, Running()),
            ]
        )

        result = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id,
            labels=[flow_concurrency_limit.name, flow_concurrency_limit_2.name],
        )

        assert len(result) == 2
        assert result[flow_concurrency_limit.name] == 9
        assert result[flow_concurrency_limit_2.name] == 9

    async def test_labels_without_limits_returns_empty_dict(
        self, tenant_id: str, labeled_flow_id: str
    ):

        result = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=["foo", "bar"]
        )

        assert result == {}

    async def test_limited_flow_runs_have_capacity(
        self, tenant_id: str, flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):

        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=[flow_concurrency_limit.name]
        )
        assert len(available_limits) == 1
        assert (
            available_limits[flow_concurrency_limit.name]
            == flow_concurrency_limit.limit
        )

    async def test_recognizes_env_labels(
        self,
        tenant_id: str,
        labeled_flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
        set_flow_run_concurrency_limits_to_10,
    ):
        """
        Tests to make sure that concurrent flows are limited by
        the labels on a Flow's environment if no
        other labels are present.
        """
        # Make sure we can actually see the change

        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=[flow_concurrency_limit.name]
        )
        assert available_limits[flow_concurrency_limit.name] == 10
        # Create a new flow run on a labeled flow and make sure it counts
        # against our available slots
        labeled_flow_run_id = await api.runs.create_flow_run(labeled_flow_id)
        await api.states.set_flow_run_state(labeled_flow_run_id, Running())

        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=[flow_concurrency_limit.name]
        )
        assert available_limits[flow_concurrency_limit.name] == 9

    async def test_recognizes_flow_group_labels(
        self,
        tenant_id: str,
        flow_id: str,
        flow_group_id: str,
        flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
        set_flow_run_concurrency_limits_to_10,
    ):
        """
        Tests to make sure that running flow runs for flows with
        flow group labels are limited by the flow concurrency limits
        of those labels.
        """

        await self.set_flow_group_labels(flow_group_id)

        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=[flow_concurrency_limit.name]
        )
        assert available_limits[flow_concurrency_limit.name] == 10
        # Create a new flow run on a labeled flow and make sure it counts
        # against our available slots

        await api.states.set_flow_run_state(flow_run_id, Running())

        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=[flow_concurrency_limit.name]
        )
        assert available_limits[flow_concurrency_limit.name] == 9

    async def test_counts_both_label_sources(
        self,
        tenant_id: str,
        labeled_flow_id: str,
        labeled_flow_run_id: str,
        flow_id: str,
        flow_group_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
        flow_concurrency_limit_2: models.FlowConcurrencyLimit,
        set_flow_run_concurrency_limits_to_10,
    ):
        """
        This test should ensure that if there are labels on both a flow group
        and an environment (for different flows), that the runs of both flows
        are counted towards the available limits.

        "foo" and "bar" should be counted once each because they exist
            on the `labeled_flow`. They don't exist on the labeled_flow_group
        "baz" should be counted once because it exists on the flow_group labels,
            and does not exist an environment.
        """
        third_limit_name = "baz"
        third_limit_limit = 10
        flow_run_id, *_ = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id=flow_id),
                self.set_flow_group_labels(flow_group_id, labels=[third_limit_name]),
                api.concurrency_limits.update_flow_concurrency_limit(
                    tenant_id=tenant_id, name=third_limit_name, limit=third_limit_limit
                ),
            ]
        )

        # All limits should have 10 slots, since there are no running slots
        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id,
            labels=[
                flow_concurrency_limit.name,
                flow_concurrency_limit_2.name,
                third_limit_name,
            ],
        )

        assert len(available_limits) == 3
        assert available_limits[flow_concurrency_limit.name] == 10
        assert available_limits[flow_concurrency_limit_2.name] == 10
        assert available_limits[third_limit_name] == third_limit_limit

        # Both "foo" and "bar" should have 9 slots because `flow_run_id_2` is running
        # and taking up one slot of each
        await api.states.set_flow_run_state(labeled_flow_run_id, Running())
        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id,
            labels=[
                flow_concurrency_limit.name,
                flow_concurrency_limit_2.name,
                third_limit_name,
            ],
        )

        assert len(available_limits) == 3
        assert available_limits[flow_concurrency_limit.name] == 9
        assert available_limits[flow_concurrency_limit_2.name] == 9
        assert available_limits[third_limit_name] == third_limit_limit

        # Baz should now take up a slot since there's one running flow run
        await api.states.set_flow_run_state(flow_run_id, Running())
        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id,
            labels=[
                flow_concurrency_limit.name,
                flow_concurrency_limit_2.name,
                third_limit_name,
            ],
        )

        assert len(available_limits) == 3
        assert available_limits[flow_concurrency_limit.name] == 9
        assert available_limits[flow_concurrency_limit_2.name] == 9
        assert available_limits[third_limit_name] == third_limit_limit - 1

    async def test_doesnt_double_count_used_slots_if_both_labeled(self):
        pass

    async def test_label_not_in_output_if_not_limited(
        self, tenant_id: str, flow_id: str, flow_group_id: str,
    ):

        await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id),
                self.set_flow_group_labels(flow_group_id),
            ]
        )

        # No limits were created for these labels, so they shouldn't
        # exist in the output dictionary
        available_limits = await api.concurrency_limits.get_available_flow_run_concurrency(
            tenant_id=tenant_id, labels=["foo", "bar"]
        )

        assert available_limits == {}

    async def test_only_counts_running_states(self):
        pass

    async def test_tenants_dont_overlap(self):
        pass


class TestUpdateFlowConcurrencyLimit:
    async def test_updates_existing_limit(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        # Making sure the fixture hasn't changed and this test actually still
        # tests what it's supposed to.
        assert flow_concurrency_limit.limit != 2
        concurrency_id = await api.concurrency_limits.update_flow_concurrency_limit(
            tenant_id=flow_concurrency_limit.tenant_id,
            name=flow_concurrency_limit.name,
            limit=2,
        )
        assert concurrency_id == flow_concurrency_limit.id

        refreshed_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"limit"})

        assert refreshed_limit.limit == 2

    async def test_creates_if_not_exists(self, tenant_id):

        created_id = await api.concurrency_limits.update_flow_concurrency_limit(
            tenant_id=tenant_id, name="doesn't exist yet", limit=5
        )
        created_limit = await models.FlowConcurrencyLimit.where(id=created_id).first(
            {"id", "name", "limit", "tenant_id"}
        )
        assert created_limit.id == created_id
        assert created_limit.name == "doesn't exist yet"
        assert created_limit.limit == 5
        assert created_limit.tenant_id == tenant_id

        assert await models.FlowConcurrencyLimit.where().count() == 1

    @pytest.mark.parametrize("limit", [-1, 0])
    async def test_cant_create_with_bad_limit(self, tenant_id, limit: int):
        with pytest.raises(ValueError):
            await api.concurrency_limits.update_flow_concurrency_limit(
                tenant_id=tenant_id, name="name doesn't matter", limit=limit
            )

    @pytest.mark.parametrize("limit", [-1, 0])
    async def test_cant_update_with_bad_limit(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit, limit: int
    ):
        with pytest.raises(ValueError):
            await api.concurrency_limits.update_flow_concurrency_limit(
                tenant_id=flow_concurrency_limit.tenant_id,
                name=flow_concurrency_limit.name,
                limit=limit,
            )

    async def test_doesnt_update_existing_on_new_name(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        old_limits = await models.FlowConcurrencyLimit.where().count()
        assert old_limits == 1
        assert flow_concurrency_limit.limit == 1
        created_id = await api.concurrency_limits.update_flow_concurrency_limit(
            tenant_id=flow_concurrency_limit.tenant_id,
            name="not a valid limit name",
            limit=2,
        )
        # Making sure we create a new one, not operating on existing
        assert created_id != flow_concurrency_limit.id
        refreshed_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"limit"})
        assert await models.FlowConcurrencyLimit.where().count() == (old_limits + 1)
        assert refreshed_limit.limit == 1

    async def test_cant_overwrite_other_tenants_limits(self, flow_concurrency_limit):
        second_tenant_id = await api.tenants.create_tenant(
            name="flow_concurrency_tests"
        )

        new_limit_id = await api.concurrency_limits.update_flow_concurrency_limit(
            tenant_id=second_tenant_id,
            name=flow_concurrency_limit.name,
            limit=flow_concurrency_limit.limit + 1,
        )
        new_limit = await models.FlowConcurrencyLimit.where(id=new_limit_id).first(
            {"id", "name", "tenant_id", "limit"}
        )

        # Refresh to check for changes
        flow_concurrency_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"id", "name", "tenant_id", "limit"})

        # Able to have the same named limits but different tenants
        assert new_limit.name == flow_concurrency_limit.name
        assert new_limit.id != flow_concurrency_limit.id

        # Make sure they don't overwrite the actual limit value
        assert new_limit.limit != flow_concurrency_limit.limit


class TestDeleteFlowConcurrencyLimit:
    async def test_delete_existing(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()
        deleted = await api.concurrency_limits.delete_flow_concurrency_limit(
            flow_concurrency_limit.id
        )
        assert deleted is True

        new_concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        assert concurrency_limit_count == (new_concurrency_limit_count + 1)

    async def test_delete_missing_id(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        deleted = await api.concurrency_limits.delete_flow_concurrency_limit(
            str(uuid.uuid4())
        )
        assert deleted is False

        new_concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        assert concurrency_limit_count == new_concurrency_limit_count
