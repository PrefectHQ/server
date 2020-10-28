import uuid

import prefect
from prefect import api, models
from prefect.utilities.graphql import compress


class TestCreateFlow:
    create_flow_mutation = """
        mutation($input: create_flow_input!) {
            create_flow(input: $input) {
                id
            }
        }
    """

    create_compressed_flow_mutation = """
        mutation($input: create_flow_from_compressed_string_input!) {
            create_flow_from_compressed_string(input: $input) {
                id
            }
        }
    """

    async def test_create_flow(self, run_query, project_id):
        serialized_flow = prefect.Flow(
            name="test", tasks=[prefect.Task(), prefect.Task()]
        ).serialize(build=False)

        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(serialized_flow=serialized_flow, project_id=project_id)
            ),
        )
        assert await models.Flow.exists(result.data.create_flow.id)
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"project_id"}
        )
        assert flow.project_id == project_id

    async def test_create_compressed_flow(self, run_query, project_id):
        serialized_flow = compress(prefect.Flow(name="test").serialize(build=False))
        result = await run_query(
            query=self.create_compressed_flow_mutation,
            variables=dict(
                input=dict(serialized_flow=serialized_flow, project_id=project_id)
            ),
        )
        assert await models.Flow.exists(
            result.data.create_flow_from_compressed_string.id
        )
        flow = await models.Flow.where(
            id=result.data.create_flow_from_compressed_string.id
        ).first({"project_id", "name"})
        assert flow.project_id == project_id
        assert flow.name == "test"

    async def test_create_compressed_flow_with_invalid_string(
        self, run_query, project_id
    ):
        serialized_flow = "42"
        result = await run_query(
            query=self.create_compressed_flow_mutation,
            variables=dict(
                input=dict(serialized_flow=serialized_flow, project_id=project_id)
            ),
        )
        assert result.errors
        assert "Unable to decompress" in result.errors[0]["message"]

    async def test_create_flow_with_version_group(self, run_query, project_id):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        version_group_id = "hello"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=serialized_flow,
                    project_id=project_id,
                    version_group_id=version_group_id,
                )
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            selection_set={"version_group_id"}
        )
        assert flow.version_group_id == version_group_id

    async def test_create_flow_respects_core_version(self, run_query, project_id):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        serialized_flow["__version__"] = "0.7.0+g5892"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(serialized_flow=serialized_flow, project_id=project_id)
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"core_version"}
        )
        assert flow.core_version == "0.7.0+g5892"

    async def test_create_flow_with_description(self, run_query, project_id):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        description = "test"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=serialized_flow,
                    project_id=project_id,
                    description=description,
                )
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"description"}
        )
        assert flow.description == description

    async def test_create_flow_with_idempotency_key(self, run_query, project_id):
        serialized_flow = prefect.Flow(name="test").serialize(build=False)
        idempotency_key = "test"
        result = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=serialized_flow,
                    project_id=project_id,
                    idempotency_key=idempotency_key,
                )
            ),
        )
        flow = await models.Flow.where(id=result.data.create_flow.id).first(
            {"flow_group": {"settings"}}
        )
        assert flow.flow_group.settings["idempotency_key"] == idempotency_key

    async def test_create_flow_autodetects_version_group(
        self, run_query, project_id, project_id_2
    ):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id,
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id,
                )
            ),
        )

        # different name!
        result3 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test-different").serialize(
                        build=False
                    ),
                    project_id=project_id,
                )
            ),
        )

        # different project!
        result4 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id_2,
                )
            ),
        )
        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            {"version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            {"version_group_id"}
        )
        flow3 = await models.Flow.where(id=result3.data.create_flow.id).first(
            {"version_group_id"}
        )
        flow4 = await models.Flow.where(id=result4.data.create_flow.id).first(
            {"version_group_id"}
        )
        assert flow1.version_group_id == flow2.version_group_id
        assert flow1.version_group_id != flow3.version_group_id
        assert flow1.version_group_id != flow4.version_group_id

    async def test_old_versions_are_automatically_archived(
        self, run_query, project_id, project_id_2
    ):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id,
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id,
                )
            ),
        )

        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"archived", "version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            selection_set={"archived"}
        )

        assert flow1.archived
        assert not flow2.archived

        result3 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id_2,
                    version_group_id=flow1.version_group_id,
                )
            ),
        )

        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"archived", "version_group_id"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            selection_set={"archived"}
        )
        flow3 = await models.Flow.where(id=result3.data.create_flow.id).first(
            selection_set={"archived"}
        )
        assert flow1.archived
        assert flow2.archived
        assert not flow3.archived

    async def test_schedule_is_activated(self, run_query, project_id):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(
                        name="test",
                        schedule=prefect.schedules.CronSchedule("0 0 * * *"),
                    ).serialize(build=False),
                    project_id=project_id,
                )
            ),
        )
        flow = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"is_schedule_active"}
        )
        assert flow.is_schedule_active

    async def test_schedule_is_not_activated_if_param_passed(
        self, run_query, project_id
    ):
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(
                        name="test",
                        schedule=prefect.schedules.CronSchedule("0 0 * * *"),
                    ).serialize(build=False),
                    project_id=project_id,
                    set_schedule_active=False,
                )
            ),
        )
        flow = await models.Flow.where(id=result1.data.create_flow.id).first(
            selection_set={"is_schedule_active"}
        )
        assert not flow.is_schedule_active

    async def test_create_flow_allows_setting_version_group_explicitly(
        self, run_query, project_id
    ):
        version_group_id = str(uuid.uuid4())
        result1 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test").serialize(build=False),
                    project_id=project_id,
                    version_group_id=version_group_id,
                )
            ),
        )
        result2 = await run_query(
            query=self.create_flow_mutation,
            variables=dict(
                input=dict(
                    serialized_flow=prefect.Flow(name="test-different").serialize(
                        build=False
                    ),
                    project_id=project_id,
                    version_group_id=version_group_id,
                )
            ),
        )
        flow1 = await models.Flow.where(id=result1.data.create_flow.id).first(
            {"version_group_id", "archived"}
        )
        flow2 = await models.Flow.where(id=result2.data.create_flow.id).first(
            {"version_group_id", "archived"}
        )
        assert flow1.version_group_id == flow2.version_group_id
        assert flow1.archived
        assert not flow2.archived


class TestDeleteFlow:
    mutation = """
        mutation($input: delete_flow_input!) {
            delete_flow(input: $input) {
                success
            }
        }
    """

    async def test_delete_flow(self, run_query, flow_id):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id)),
        )
        assert not await models.Flow.exists(flow_id)


class TestArchiveFlow:
    mutation = """
        mutation($input: archive_flow_input!) {
            archive_flow(input: $input) {
                success
            }
        }
    """

    async def test_archive_flow(self, run_query, flow_id):
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id)),
        )
        # confirm the payload is as expected
        assert result.data.archive_flow.success is True
        # confirm that success is reflected in the DB as well
        flow = await models.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_nonexistent_flow(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=str(uuid.uuid4()))),
        )
        # confirm the payload is as expected
        assert result.data.archive_flow.success is False

    async def test_archive_flow_with_none_flow_id(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=None)),
        )
        assert (
            "Expected non-nullable type UUID! not to be None."
            in result.errors[0].message
        )


class TestUpdateFlowProject:
    mutation = """
        mutation($input: update_flow_project_input!) {
            update_flow_project(input: $input) {
                id
            }
        }
    """

    async def test_update_flow_project(self, run_query, tenant_id, flow_id):
        # create the destination project
        project_2 = await api.projects.create_project(
            tenant_id=tenant_id, name="Astral Project-ion"
        )
        # confirm the flow's project isn't the same as the newly-created project
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id != project_2
        # update the flow
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, project_id=project_2)),
        )
        assert result.data.update_flow_project.id == flow_id
        # confirm the value was updated
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_2

    async def test_update_flow_project_fails_with_invalid_project_id(
        self, run_query, flow_id, project_id
    ):
        project_2 = str(uuid.uuid4())
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, project_id=project_2)),
        )
        assert "Invalid flow or project ID" in result.errors[0].message
        # confirm the project ID wasn't updated
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id

    async def test_update_flow_project_fails_with_none_project_id(
        self, run_query, flow_id, project_id
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, project_id=None)),
        )
        assert "Variable '$input' got invalid value" in result.errors[0].message
        # confirm the project ID wasn't updated
        flow = await models.Flow.where(id=flow_id).first({"project_id"})
        assert flow.project_id == project_id


class TestUpdateFlowHeartbeat:
    enable_heartbeat_mutation = """
        mutation($input: enable_flow_heartbeat_input!) {
            enable_flow_heartbeat(input: $input) {
                success
            }
        }
    """

    disable_heartbeat_mutation = """
        mutation($input: disable_flow_heartbeat_input!) {
            disable_flow_heartbeat(input: $input) {
                success
            }
        }
    """

    async def test_enable_flow_heartbeat(self, run_query, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("heartbeat_enabled", False) is False

        result = await run_query(
            query=self.enable_heartbeat_mutation,
            variables=dict(input={"flow_id": flow_id}),
        )
        assert result.data.enable_flow_heartbeat.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {
            "heartbeat_enabled": True,
            "disable_heartbeat": False,
        }

    async def test_disable_flow_heartbeat(self, run_query, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"heartbeat_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("heartbeat_enabled", True) is True

        result = await run_query(
            query=self.disable_heartbeat_mutation,
            variables=dict(input={"flow_id": flow_id}),
        )
        assert result.data.disable_flow_heartbeat.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {
            "heartbeat_enabled": False,
            "disable_heartbeat": True,
        }

    async def test_disable_flow_heartbeat__where_flow_id_none(self, run_query):
        result = await run_query(
            query=self.disable_heartbeat_mutation,
            variables=dict(input={"flow_id": None}),
        )
        # confirm there was an error, and that it was related to flow_id=None
        assert "got invalid value None at 'input.flow_id'" in result.errors[0].message

    async def test_enable_flow_heartbeat_where_flow_id_none(self, run_query):
        result = await run_query(
            query=self.enable_heartbeat_mutation,
            variables=dict(input={"flow_id": None}),
        )
        # confirm there was an error, and that it was related to flow_id=None
        assert "got invalid value None at 'input.flow_id'" in result.errors[0].message


class TestUpdateFlowLazarus:
    enable_lazarus_mutation = """
        mutation($input: enable_flow_lazarus_process_input!) {
            enable_flow_lazarus_process(input: $input) {
                success
            }
        }
    """

    disable_lazarus_mutation = """
        mutation($input: disable_flow_lazarus_process_input!) {
            disable_flow_lazarus_process(input: $input) {
                success
            }
        }
    """

    async def test_enable_flow_lazarus_process(self, run_query, flow_id, flow_group_id):
        await models.FlowGroup.where(id=flow_group_id).update({"settings": {}})
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", False) is False

        result = await run_query(
            query=self.enable_lazarus_mutation,
            variables=dict(input={"flow_id": flow_id}),
        )
        assert result.data.enable_flow_lazarus_process.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": True}

    async def test_disable_flow_lazarus_process(
        self, run_query, flow_id, flow_group_id
    ):
        await models.FlowGroup.where(id=flow_group_id).update(
            {"settings": {"lazarus_enabled": True}}
        )
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings.get("lazarus_enabled", True) is True

        result = await run_query(
            query=self.disable_lazarus_mutation,
            variables=dict(input={"flow_id": flow_id}),
        )
        assert result.data.disable_flow_lazarus_process.success is True
        flow_group = await models.FlowGroup.where(id=flow_group_id).first({"settings"})
        assert flow_group.settings == {"lazarus_enabled": False}

    async def test_disable_flow_lazarus_process_where_flow_id_none(self, run_query):
        result = await run_query(
            query=self.disable_lazarus_mutation,
            variables=dict(input={"flow_id": None}),
        )
        # confirm there was an error, and that it was related to flow_id=None
        assert "got invalid value None at 'input.flow_id'" in result.errors[0].message

    async def test_enable_flow_lazarus_where_flow_id_none(self, run_query):
        result = await run_query(
            query=self.enable_lazarus_mutation,
            variables=dict(input={"flow_id": None}),
        )
        # confirm there was an error, and that it was related to flow_id=None
        assert "got invalid value None at 'input.flow_id'" in result.errors[0].message


class TestSetScheduleActive:
    mutation = """
        mutation($input: set_schedule_active_input!) {
            set_schedule_active(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_schedule_active(self, run_query, flow_id):
        await api.flows.set_schedule_inactive(flow_id=flow_id)

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id)),
        )

        assert result.data.set_schedule_active.success is True
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert flow.is_schedule_active


class TestSetScheduleInactive:
    mutation = """
        mutation($input: set_schedule_inactive_input!) {
            set_schedule_inactive(input: $input) {
                success
            }
        }
    """

    async def test_set_flow_schedule_inactive(self, run_query, flow_id):
        await api.flows.set_schedule_active(flow_id=flow_id)

        # set inactive
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id)),
        )
        assert result.data.set_schedule_inactive.success is True
        flow = await models.Flow.where(id=flow_id).first({"is_schedule_active"})
        assert not flow.is_schedule_active
