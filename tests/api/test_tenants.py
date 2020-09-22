import uuid

import pytest

from prefect import api, models


def random_id() -> str:
    return str(uuid.uuid4())


class TestCreateTenant:
    async def test_create_tenant(self):
        name = random_id()
        slug = random_id()

        tenant_id = await api.tenants.create_tenant(name=name, slug=slug)
        assert await models.Tenant.exists(tenant_id)

    async def test_create_tenant_stores_attributes(self):
        name = random_id()
        slug = random_id()
        tenant_id = await api.tenants.create_tenant(name=name, slug=slug)
        tenant = await models.Tenant.where(id=tenant_id).first({"id", "name", "slug"})
        assert tenant.id == tenant_id
        assert tenant.name == name
        assert tenant.slug == slug

    async def test_create_tenant_fails_with_duplicate_slug(self):
        await api.tenants.create_tenant(name="hi", slug="slug")
        with pytest.raises(ValueError) as exc:
            await api.tenants.create_tenant(name="hi again", slug="slug")
        assert "Uniqueness violation" in str(exc.value)

    async def test_create_tenant_with_default_slug(self):
        name = "Hello there"

        tenant_id = await api.tenants.create_tenant(name=name)

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        assert tenant.slug == "hello-there"

    async def test_create_tenant_fails_with_duplicate_default_slug(self):
        await api.tenants.create_tenant(name="hi")
        with pytest.raises(ValueError) as exc:
            await api.tenants.create_tenant(name="hi")
        assert "Uniqueness violation" in str(exc.value)

    async def test_create_tenant_with_complex_slug_fails(self):
        name = random_id()

        with pytest.raises(ValueError) as exc:
            await api.tenants.create_tenant(name=name, slug="hello there")

        assert 'Slug must be "slugified"' in str(exc.value)


class TestTenantSettings:
    async def test_update_settings(self, tenant_id):
        tenant = await models.Tenant.where(id=tenant_id).first("settings")
        assert tenant.settings == {}
        assert await api.tenants.update_settings(
            tenant_id=tenant_id, settings={"x": "y"}
        )
        tenant = await models.Tenant.where(id=tenant_id).first("settings")
        assert tenant.settings == {"x": "y"}

    async def test_update_settings_without_overwriting(self, tenant_id):
        tenant = await models.Tenant.where(id=tenant_id).first("settings")
        assert tenant.settings == {}
        assert await api.tenants.update_settings(
            tenant_id=tenant_id, settings={"x": "y"}
        )
        assert await api.tenants.update_settings(
            tenant_id=tenant_id, settings={"a": "b"}
        )
        tenant = await models.Tenant.where(id=tenant_id).first("settings")
        assert tenant.settings == {"x": "y", "a": "b"}

    async def test_update_settings_with_bad_user_id(self):
        with pytest.raises(ValueError) as exc:
            await api.tenants.update_settings(
                tenant_id=str(uuid.uuid4()), settings={"a": "b"}
            )
        assert "Invalid tenant id" in str(exc.value)


class TestUpdateTenantName:
    async def test_tenant_name(self, tenant_id):
        assert await api.tenants.update_name(tenant_id=tenant_id, name="new name")

        tenant = await models.Tenant.where(id=tenant_id).first({"name"})
        assert tenant.name == "new name"


class TestUpdateTenantSlug:
    async def test_tenant_slug(self, tenant_id):
        assert await api.tenants.update_slug(tenant_id=tenant_id, slug="new-slug")

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        assert tenant.slug == "new-slug"

    async def test_invalid_tenant_slug_fails(self, tenant_id):
        with pytest.raises(ValueError, match=r"Slug must be \"slugified\""):
            assert await api.tenants.update_slug(tenant_id=tenant_id, slug="new slug")

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        assert tenant.slug == "test-tenant"

    async def test_duplicate_slug_fails(self, tenant_id):
        await api.tenants.create_tenant(name="a new tenant", slug="a-new-slug")

        with pytest.raises(ValueError, match="Uniqueness violation"):
            assert await api.tenants.update_slug(tenant_id=tenant_id, slug="a-new-slug")

        tenant = await models.Tenant.where(id=tenant_id).first({"slug"})
        assert tenant.slug == "test-tenant"


class TestDeleteTenant:
    async def test_delete_tenant(self, tenant_id):
        result = await api.tenants.delete_tenant(tenant_id=tenant_id)
        tenant = await models.Tenant.where(id=tenant_id).first()

        assert result is True
        assert tenant is None

    async def test_delete_tenant_fails_with_invalid_id(self):
        result = await api.tenants.delete_tenant(tenant_id=str(uuid.uuid4()))
        assert result is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, ""],
    )
    async def test_delete_tenant_fails_if_none(self, bad_value):
        with pytest.raises(ValueError, match="Invalid tenant ID"):
            await api.tenants.delete_tenant(tenant_id=bad_value)
