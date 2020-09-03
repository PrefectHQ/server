import datetime
import uuid

import pendulum
import pydantic
import pytest

import prefect
from prefect.utilities.graphql import EnumValue
from prefect import api
from prefect import models


class TestUpdateFlowHeartbeat:
    async def test_disable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flows.disable_heartbeat_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is False
        assert flow_group.settings["disable_heartbeat"] is True

    async def test_enable_heartbeat_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})

        assert flow_group.settings == {}
        assert await api.flows.enable_heartbeat_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings["heartbeat_enabled"] is True
        assert flow_group.settings["disable_heartbeat"] is False

    async def test_disable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_heartbeat_for_flow(flow_id=None)

    async def test_enable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_heartbeat_for_flow(flow_id=None)


class TestUpdateLazarusForFlow:
    async def test_disable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", False) is True
        assert await api.flows.disable_lazarus_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": False}

    async def test_enable_lazarus_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": False}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", True) is False
        assert await api.flows.enable_lazarus_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": True}

    async def test_disable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_lazarus_for_flow(flow_id=None)

    async def test_enable_lazarus_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_lazarus_for_flow(flow_id=None)


class TestUpdateVersionLockingForFlow:
    async def test_disable_version_locking_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"version_locking_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("version_locking_enabled", False) is True
        assert await api.flows.disable_version_locking_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"version_locking_enabled": False}

    async def test_enable_version_locking_for_flow(self, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"version_locking_enabled": False}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("version_locking_enabled", True) is False
        assert await api.flows.enable_version_locking_for_flow(flow_id=flow_id)

        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"version_locking_enabled": True}

    async def test_disable_version_locking_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.disable_version_locking_for_flow(flow_id=None)

    async def test_enable_version_locking_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await api.flows.enable_version_locking_for_flow(flow_id=None)
