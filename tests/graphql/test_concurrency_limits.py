import uuid

from prefect import api
from prefect_server.database import models


class TestUpdateFlowConcurrencyLimit:
    mutation = """
        mutation($input: update_flow_concurrency_limit_input!) {
            update_flow_concurrency_limit(input: $input) {
                id
            }
        }
    """

    async def test_creates_if_not_exists(self, run_query, tenant_id: str):
        name = "test"
        limit = 5
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(tenant_id=tenant_id, name=name, limit=limit)),
        )

        limit_id = result.data.update_flow_concurrency_limit.id

        flow_concurrency_limit = await models.FlowConcurrencyLimit.where(
            id=limit_id
        ).first({"id", "name", "limit", "tenant_id"})

        assert flow_concurrency_limit.id == limit_id
        assert flow_concurrency_limit.name == name
        assert flow_concurrency_limit.limit == limit
        assert flow_concurrency_limit.tenant_id == tenant_id

    async def test_updates_if_exists(
        self, run_query, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        old_limit = flow_concurrency_limit.limit
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=flow_concurrency_limit.tenant_id,
                    name=flow_concurrency_limit.name,
                    limit=old_limit + 1,
                )
            ),
        )

        assert result.data.update_flow_concurrency_limit.id == flow_concurrency_limit.id
        # Updates, not creates new
        assert await models.FlowConcurrencyLimit.where().count() == 1

        flow_concurrency_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"id", "name", "limit", "tenant_id"})

        assert flow_concurrency_limit.limit == old_limit + 1

    async def test_no_op_if_already_matching(
        self, run_query, flow_concurrency_limit: models.FlowConcurrencyLimit
    ):
        old_limit = flow_concurrency_limit.limit

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=flow_concurrency_limit.tenant_id,
                    name=flow_concurrency_limit.name,
                    limit=flow_concurrency_limit.limit,
                )
            ),
        )

        assert result.data.update_flow_concurrency_limit.id == flow_concurrency_limit.id
        # Updates, not creates new
        assert await models.FlowConcurrencyLimit.where().count() == 1

        flow_concurrency_limit = await models.FlowConcurrencyLimit.where(
            id=flow_concurrency_limit.id
        ).first({"id", "name", "limit", "tenant_id"})

        # Making sure we don't actually change anything!
        assert flow_concurrency_limit.limit == old_limit

    async def test_errors_with_bad_limit(self, run_query, tenant_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    tenant_id=tenant_id,
                    name="this will error because of the negative limit",
                    limit=-5,
                )
            ),
        )

        assert result.errors


class TestDeleteFlowConcurrencyLimit:
    mutation = """
        mutation($input: delete_flow_concurrency_limit_input!) {
            delete_flow_concurrency_limit(input: $input) {
                success
            }
        }
    """

    async def test_deletes_existing(self, run_query, flow_concurrency_limit_id: str):

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(limit_id=flow_concurrency_limit_id)),
        )
        assert result.data.delete_flow_concurrency_limit.success
        assert await models.FlowConcurrencyLimit.where().count() == 0

    async def test_delete_missing(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(limit_id=str(uuid.uuid4()))),
        )

        assert result.errors

        # There weren't any limits to delete, but doesn't hurt to check :)
        assert await models.FlowConcurrencyLimit.where().count() == 0
