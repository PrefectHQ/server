import asyncio
import uuid
from typing import List, Optional

import pendulum
import pytest

import prefect
from prefect.engine.state import Running, Submitted
from prefect import api, models

state_schema = prefect.serialization.state.StateSchema()


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


class TestTryTakeFlowConcurrencySlots:
    async def test_submitted_already_occupies_slot(
        self,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        Tests to make sure that if a `flow_run_id` is provided,
        the check to confirm whether the run is already occupying
        a concurrency slot is executed.
        """
        await api.states.set_flow_run_state(labeled_flow_run_id, Submitted())

        is_occupying_slot_already = (
            await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                tenant_id=flow_concurrency_limit.tenant_id,
                limit_names=[flow_concurrency_limit.name],
                flow_run_id=labeled_flow_run_id,
            )
        )

        assert is_occupying_slot_already is True

    async def test_returns_true_when_slots_available(
        self, labeled_flow_id: str, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        """
        Tests to make sure that if there are a non-zero
        amount of concurrency slots available, that the
        check returns True and doesn't do any stateful
        counting.
        """
        runs = await asyncio.gather(
            *[
                api.runs.create_flow_run(
                    labeled_flow_id, labels=[flow_concurrency_limit.name]
                )
                for _ in range(5)
            ]
        )

        can_occupy_slot = await asyncio.gather(
            *[
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=flow_concurrency_limit.tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                )
            ]
        )

        assert all(can_occupy_slot) is True

    async def test_returns_false_when_slots_unavailable(
        self,
        labeled_flow_run_id: str,
        labeled_flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        # No slots left after this transition
        await api.states.set_flow_run_state(labeled_flow_run_id, Running())

        runs = await asyncio.gather(
            *[
                api.runs.create_flow_run(
                    labeled_flow_id, labels=[flow_concurrency_limit.name]
                )
                for _ in range(5)
            ]
        )

        can_occupy_slot = await asyncio.gather(
            *[
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=flow_concurrency_limit.tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                    flow_run_id=run_id,
                )
                for run_id in runs
            ]
        )

        assert all(can_occupy_slot) is False

    @pytest.mark.parametrize("pass_id", [False, True])
    async def test_returns_true_when_unlimited_label(
        self, tenant_id: str, flow_run_id: str, pass_id: bool
    ):

        if pass_id:
            can_occupy_slot = (
                await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id,
                    limit_names=["foo", "bar"],
                    flow_run_id=flow_run_id,
                )
            )
        else:
            can_occupy_slot = (
                await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id, limit_names=["foo", "bar"]
                )
            )

        assert can_occupy_slot is True

    @pytest.mark.parametrize("pass_id", [False, True])
    @pytest.mark.parametrize("labels", [[], None])
    async def test_empty_labels_returns_true(
        self, tenant_id: str, flow_run_id: str, labels: Optional[List], pass_id: bool
    ):
        """
        Tests to ensure that any flow runs without `labels` (empty or None)
        always returns True since those runs aren't labeled.
        """

        if pass_id:
            can_occupy_slot = (
                await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id,
                    limit_names=labels,
                    flow_run_id=flow_run_id,
                )
            )
        else:
            can_occupy_slot = (
                await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id, limit_names=labels
                )
            )

        assert can_occupy_slot is True

    async def test_filters_by_tenant(
        self,
        tenant_id: str,
        flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        first_run_id, second_run_id = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name])
                for _ in range(2)
            ]
        )
        await api.states.set_flow_run_state(first_run_id, Running())
        # For this tenant, we shouldn't be able to take any more slots
        assert not await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
            tenant_id=flow_concurrency_limit.tenant_id,
            limit_names=[flow_concurrency_limit.name],
        )
        assert not await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
            tenant_id=flow_concurrency_limit.tenant_id,
            limit_names=[flow_concurrency_limit.name],
            flow_run_id=second_run_id,
        )

        second_tenant_id = await api.tenants.create_tenant(name="other test tenant")
        other_project_id = await api.projects.create_project(
            tenant_id=second_tenant_id, name="Other tenant's project"
        )

        flow_id = await api.flows.create_flow(
            project_id=other_project_id,
            serialized_flow=prefect.Flow(name="other test flow").serialize(),
        )

        runs = await asyncio.gather(
            *[api.runs.create_flow_run(flow_id=flow_id) for _ in range(5)]
        )

        can_occupy_slot = await asyncio.gather(
            *[
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=second_tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                    flow_run_id=run_id,
                )
                for run_id in runs
            ]
        )

        assert all(can_occupy_slot) is True

    async def test_can_transition_from_submitted_to_running(
        self,
        tenant_id: str,
        labeled_flow_run_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):

        can_transition_to_submitted = (
            await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                tenant_id=tenant_id,
                limit_names=[flow_concurrency_limit.name],
                flow_run_id=labeled_flow_run_id,
            )
        )

        assert can_transition_to_submitted is True

        await api.states.set_flow_run_state(labeled_flow_run_id, Submitted())

        can_transition_to_running = (
            await api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                tenant_id=tenant_id,
                limit_names=[flow_concurrency_limit.name],
                flow_run_id=labeled_flow_run_id,
            )
        )

        assert can_transition_to_running is True

    async def test_race_condition_over_allocated_concurrency(
        self,
        tenant_id: str,
        flow_id: str,
        flow_concurrency_limit: models.FlowConcurrencyLimit,
    ):
        """
        This test should cover the race condition where we 2 flow runs
        accidentally end up in the `Submitted` state, even though there should
        only be one in that state and the other should have failed. In this case,
        when transitioning from `Submitted` -> `Running`, the first of the
        two should realize it's over the concurrency limit and get set to `Queued`,
        and the second should transition to `Running` (since the first is no longer
        utilizing the slots)
        """

        first_run, second_run = await asyncio.gather(
            *[
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
                api.runs.create_flow_run(flow_id, labels=[flow_concurrency_limit.name]),
            ]
        )

        # First setting should work
        await api.states.set_flow_run_state(first_run, Submitted())

        # This is effectively recreating `set_flow_run_state` without
        # all the logic protecting against exactly what we're doing
        # here.

        ## Duplicated code

        second_flow_run = await models.FlowRun.where(id=second_run).first(
            {
                "id": True,
                "serialized_state": True,
                "version": True,
            }
        )
        existing_state = state_schema.load(second_flow_run.serialized_state)
        state = Submitted(
            state=existing_state,
            message="Submitted outside of standard API to avoid safety checks.",
        )

        second_run_submitted_state = models.FlowRunState(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            flow_run_id=second_run,
            version=second_flow_run.version + 1,
            state=type(state).__name__,
            timestamp=pendulum.now("UTC"),
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )

        await second_run_submitted_state.insert()

        ## End duplicated code

        # This should fail, regardless of which we check

        transition_conditions = await asyncio.gather(
            *[
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                    flow_run_id=first_run,
                ),
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                    flow_run_id=second_run,
                ),
                api.flow_concurrency_limits.try_take_flow_concurrency_slots(
                    tenant_id=tenant_id,
                    limit_names=[flow_concurrency_limit.name],
                ),
            ]
        )

        assert any(transition_conditions) is False


class TestUpdateFlowConcurrencyLimit:
    async def test_updates_existing_limit(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):

        # Making sure the fixture hasn't changed and this test actually still
        # tests what it's supposed to.
        assert flow_concurrency_limit.limit != 2
        concurrency_id = (
            await api.flow_concurrency_limits.update_flow_concurrency_limit(
                tenant_id=flow_concurrency_limit.tenant_id,
                name=flow_concurrency_limit.name,
                limit=2,
            )
        )
        assert concurrency_id == flow_concurrency_limit.id

        refreshed_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"limit"})

        assert refreshed_limit.limit == 2

    async def test_creates_if_not_exists(self, tenant_id):

        created_id = await api.flow_concurrency_limits.update_flow_concurrency_limit(
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
            await api.flow_concurrency_limits.update_flow_concurrency_limit(
                tenant_id=tenant_id, name="name doesn't matter", limit=limit
            )

    @pytest.mark.parametrize("limit", [-1, 0])
    async def test_cant_update_with_bad_limit(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit, limit: int
    ):
        with pytest.raises(ValueError):
            await api.flow_concurrency_limits.update_flow_concurrency_limit(
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
        created_id = await api.flow_concurrency_limits.update_flow_concurrency_limit(
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

        new_limit_id = await api.flow_concurrency_limits.update_flow_concurrency_limit(
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
        deleted = await api.flow_concurrency_limits.delete_flow_concurrency_limit(
            flow_concurrency_limit.id
        )
        assert deleted is True

        new_concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        assert concurrency_limit_count == (new_concurrency_limit_count + 1)

    async def test_delete_missing_id(
        self, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        deleted = await api.flow_concurrency_limits.delete_flow_concurrency_limit(
            str(uuid.uuid4())
        )
        assert deleted is False

        new_concurrency_limit_count = await models.FlowConcurrencyLimit.where().count()

        assert concurrency_limit_count == new_concurrency_limit_count
