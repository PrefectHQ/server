import slugify

from prefect import models
from prefect.utilities.plugins import register_api


def verify_slug(slug: str) -> None:
    if slug != slugify.slugify(slug):
        raise ValueError('Slug must be "slugified" (lowercase; no spaces)')


@register_api("tenants.create_tenant")
async def create_tenant(name: str, slug: str = None) -> str:
    """
    Create a new tenant.

    Args:
        - name (str): the tenant name
        - slug (str): the tenant slug (must be globally unique). If None, the name is used.
            The slug must conform to "slug" specifications (lowercase, hyphenated)

    Returns:
        - str: the new tenant id
    """
    if slug is None:
        slug = slugify.slugify(name)

    verify_slug(slug)
    tenant_id = await models.Tenant(name=name, slug=slug).insert()
    return tenant_id


@register_api("tenants.update_settings")
async def update_settings(tenant_id: str, settings: dict) -> bool:
    """
    Updates a tenant's settings with the provided settings object.

    Only keys that are present in the provided settings object will be updated.

    Args:
        - tenant_id (str): the tenant id
        - settings (dict): the settings to update

    Returns:
        - bool: whether the update succeeded

    Raises:
        - ValueError: if the tenant ID is invalid
    """
    # apply tenant_admin role if possible
    tenant = await models.Tenant.where(id=tenant_id).first({"settings"})
    if not tenant:
        raise ValueError("Invalid tenant id.")

    tenant.settings.update(settings)

    # update with new current_settings
    result = await models.Tenant.where(id=tenant_id).update(
        set={"settings": tenant.settings}
    )
    return bool(result.affected_rows)


@register_api("tenants.update_name")
async def update_name(tenant_id: str, name: str) -> bool:
    """
    Updates a tenant's name.

    Args:
        - tenant_id (str): the tenant id
        - name (str): the new name

    Returns:
        - bool: whether the update succeeded
    """

    result = await models.Tenant.where(id=tenant_id).update(set={"name": name})
    return bool(result.affected_rows)


@register_api("tenants.update_slug")
async def update_slug(tenant_id: str, slug: str) -> bool:
    """
    Updates a tenant's slug.

    Args:
        - tenant_id (str): the tenant id
        - slug (str): the new slug

    Returns:
        - bool: whether the update succeeded
    """
    verify_slug(slug)
    result = await models.Tenant.where(id=tenant_id).update(set={"slug": slug})
    return bool(result.affected_rows)


@register_api("tenants.delete_tenant")
async def delete_tenant(tenant_id: str) -> bool:
    """
    Deletes a tenant.

    Args:
        - tenant_id (str): the tenant to delete

    Returns:
        - bool: if the delete succeeded

    Raises:
        - ValueError: if an ID isn't provided
    """
    if not tenant_id:
        raise ValueError("Invalid tenant ID.")

    result = await models.Tenant.where(id=tenant_id).delete()
    return bool(result.affected_rows)  # type: ignore
