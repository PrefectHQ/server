import uuid

import pytest

from prefect_server import api
from prefect_server.database import models


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

