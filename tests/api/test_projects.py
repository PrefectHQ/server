import uuid

import pytest

from prefect import api, models


class TestCreateProject:
    async def test_create_project(self, tenant_id):
        project_id = await api.projects.create_project(tenant_id=tenant_id, name="test")

        assert await models.Project.exists(project_id)
        project = await models.Project.where(id=project_id).first({"name"})
        assert project.name == "test"

    async def test_create_project_with_description(self, tenant_id):
        project_id = await api.projects.create_project(
            tenant_id=tenant_id, name="test", description="test-description"
        )

        assert await models.Project.exists(project_id)
        project = await models.Project.where(id=project_id).first(
            {"name", "description"}
        )
        assert project.name == "test"
        assert project.description == "test-description"

    async def test_create_duplicate_project(self, tenant_id):
        await api.projects.create_project(tenant_id=tenant_id, name="test")
        with pytest.raises(ValueError):
            await api.projects.create_project(tenant_id=tenant_id, name="test")

    async def test_delete_project_deletes_flow(self, project_id, flow_id, tenant_id):
        await models.Project.where(id=project_id).delete()
        assert not await models.Project.exists(flow_id)

    async def test_same_project_name_in_multiple_tenants(self, tenant_id):
        tenant_id_2 = await api.tenants.create_tenant(name="name")
        p1 = await api.projects.create_project(tenant_id=tenant_id, name="test")
        p2 = await api.projects.create_project(tenant_id=tenant_id_2, name="test")

        assert await models.Project.exists(p1)
        assert await models.Project.exists(p2)

    async def test_delete_tenant_deletes_project(self, tenant_id, project_id):
        await models.Tenant.where(id=tenant_id).delete()
        assert not await models.Project.exists(project_id)

    async def test_delete_project_does_not_delete_tenant(self, tenant_id, project_id):
        await models.Project.where(id=project_id).delete()
        assert await models.Tenant.exists(tenant_id)

    async def test_delete_project_deletes_flow(self, project_id, flow_id):
        await models.Project.where(id=project_id).delete()
        assert not await models.Project.exists(flow_id)


class TestSetProjectName:
    async def test_set_project_name(self, project_id):
        result = await api.projects.set_project_name(
            project_id=project_id, name="my-new-name"
        )
        project = await models.Project.where(id=project_id).first({"name"})

        assert result is True
        assert project.name == "my-new-name"

    async def test_set_project_name_fails_with_invalid_id(self):
        result = await api.projects.set_project_name(
            project_id=str(uuid.uuid4()), name="my-new-name"
        )
        assert result is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, ""],
    )
    async def test_set_project_name_fails_if_none(self, bad_value):
        with pytest.raises(ValueError, match="Invalid project ID"):
            await api.projects.set_project_name(
                project_id=bad_value, name="my-new-name"
            )


class TestSetProjectDescription:
    async def test_set_project_description(self, project_id):
        result = await api.projects.set_project_description(
            project_id=project_id, description="description"
        )
        project = await models.Project.where(id=project_id).first({"description"})

        assert result is True
        assert project.description == "description"

    async def test_set_project_description_fails_with_invalid_id(self):
        result = await api.projects.set_project_description(
            project_id=str(uuid.uuid4()), description="description"
        )
        assert result is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, ""],
    )
    async def test_set_project_description_fails_if_none(self, bad_value):
        with pytest.raises(ValueError, match="Invalid project ID"):
            await api.projects.set_project_description(
                project_id=bad_value, description="description"
            )


class TestDeleteProjects:
    async def test_delete_project(self, project_id):
        result = await api.projects.delete_project(project_id=project_id)
        project = await models.Project.where(id=project_id).first()

        assert result is True
        assert project is None

    async def test_delete_project_fails_with_invalid_id(self):
        result = await api.projects.delete_project(project_id=str(uuid.uuid4()))
        assert result is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, ""],
    )
    async def test_delete_project_fails_if_none(self, bad_value):
        with pytest.raises(ValueError, match="Invalid project ID"):
            await api.projects.delete_project(project_id=bad_value)
