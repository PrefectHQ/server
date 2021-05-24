import pendulum
import pytest
import uuid

from prefect import api, models
from prefect_server import config


class TestCreateAgent:
    async def test_register_agent(self, tenant_id):
        # create an agent
        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo", "bar"],
        )
        agent = await models.Agent.where(id=agent_id).first(
            {"id", "tenant_id", "labels"}
        )
        assert agent.id == agent_id
        assert agent.tenant_id == tenant_id
        assert set(agent.labels) == set(["bar", "foo"])

    @pytest.mark.parametrize("labels", [[], None])
    async def test_register_agent_with_empty_labels(self, tenant_id, labels):
        # create an agent
        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=labels,
        )
        agent = await models.Agent.where(id=agent_id).first(
            {"id", "tenant_id", "labels"}
        )
        assert agent.id == agent_id
        assert agent.tenant_id == tenant_id
        assert agent.labels == []

    async def test_register_agent_with_optional_arguments(self, tenant_id):
        labels = ["foo", "bar"]
        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id, name="MyNewAgent", type="NewAgent", labels=labels
        )
        agent = await models.Agent.where(id=agent_id).first(
            {"id", "tenant_id", "labels", "name", "type"}
        )
        assert agent.id == agent_id
        assert agent.tenant_id == tenant_id
        assert agent.name == "MyNewAgent"
        assert agent.type == "NewAgent"
        assert set(agent.labels) == set(labels)

    async def test_register_multiple_agents(self, tenant_id):
        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo", "bar"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo", "bar"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo2", "bar2"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_count = await models.Agent.where(
            {"tenant_id": {"_eq": tenant_id}}
        ).count()
        assert agent_count == 2

    async def test_register_multiple_agents_label_order(self, tenant_id):
        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo", "bar", "chris"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["chris", "bar", "foo"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["bar", "chris", "foo"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["foo", "chris", "bar"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["bar", "foo", "chris"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1

        agent_id = await api.agents.register_agent(
            tenant_id=tenant_id,
            labels=["chris", "foo", "bar"],
        )
        agent_count = await models.Agent.where(id=agent_id).count()
        assert agent_count == 1


class TestUpdateAgentLastQueried:
    async def test_update_agent_last_queried(self, agent_id):
        start_time = pendulum.now("utc")

        # Update last queried
        assert await api.agents.update_agent_last_queried(agent_id=agent_id) is True

        agent = await models.Agent.where(id=agent_id).first({"last_queried"})

        # Check last queried time
        assert start_time <= agent.last_queried <= pendulum.now("utc")

    async def test_update_agent_with_none_id_raises_error(self, agent_id):
        with pytest.raises(ValueError, match="Must supply an agent ID to update."):
            await api.agents.update_agent_last_queried(agent_id=None)


class TestDeleteAgent:
    async def test_delete_agent(self, agent_id):
        # delete the agent
        await api.agents.delete_agent(agent_id=agent_id)
        # confirm the agent was deleted
        agent = await models.Agent.where(id=agent_id).first()
        assert agent is None

    async def test_delete_agent_with_none_id_raises_error(self, agent_id):
        # confirm the error is raised as expected
        with pytest.raises(ValueError, match="Must supply an agent ID to delete."):
            await api.agents.delete_agent(agent_id=None)
        # confirm the agent still exists
        assert await models.Agent.where(id=agent_id).first() is not None


class TestAgentConcurrencyLimit:
    async def test_is_agent_at_limit_no_flow_runs(self, agent_id):
        result = await api.agents.is_agent_at_concurrency_limit(
            agent_id=agent_id, limit=1
        )
        assert result is False

    async def test_is_agent_at_limit_unknown_agent_id(self):
        result = await api.agents.is_agent_at_concurrency_limit(
            agent_id=uuid.uuid4(), limit=1
        )
        assert result is False

    async def test_is_agent_at_limit_counts_only_submitted_and_running(
        self, agent_id, flow_id
    ):
        for state in ["Running", "Submitted", "Scheduled", "Failed"]:
            flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)
            await models.FlowRun.where(id=flow_run_id).update(
                {"agent_id": agent_id, "state": state}
            )
        await models.FlowRun.where(id=flow_run_id).update(
            {"agent_id": agent_id, "state": state}
        )
        assert (
            await api.agents.is_agent_at_concurrency_limit(agent_id=agent_id, limit=3)
            is False
        )
        assert (
            await api.agents.is_agent_at_concurrency_limit(agent_id=agent_id, limit=2)
            is True
        )

    @pytest.mark.parametrize("exceeded", [True, False])
    async def test_is_agent_at_limit_when_at_or_exceeded(
        self, agent_id, flow_id, exceeded, caplog
    ):
        LIMIT = 3
        for _ in range(LIMIT + 1 if exceeded else LIMIT):
            flow_run_id = await api.runs.create_flow_run(flow_id=flow_id)
            await models.FlowRun.where(id=flow_run_id).update(
                {"agent_id": agent_id, "state": "Running"}
            )

        result = await api.agents.is_agent_at_concurrency_limit(
            agent_id=agent_id, limit=LIMIT
        )
        assert result is True
        # Log on exceeded
        assert ("surpassed concurrency limit" in caplog.text) is exceeded
