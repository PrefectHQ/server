from prefect import models
from prefect.utilities.plugins import register_api


@register_api("projects.create_project")
async def create_project(tenant_id: str, name: str, description: str = None) -> str:
    """
    Creates a project, returning its id

    Args:
        - tenant_id (str): the tenant id
        - name (str): the project name (must be unique within the tenant)
        - description (str): an optional description

    Returns:
        - str: the project id
    """
    return await models.Project(
        tenant_id=tenant_id, name=name, description=description
    ).insert()


@register_api("projects.set_project_name")
async def set_project_name(project_id: str, name: str) -> str:
    """
    Update a project's name

    Args:
        - project_id (str): the project ID
        - name (str): the name to give the provided project

    Returns:
        - str: the project ID

    Raises:
        - ValueError: if the project doesn't exist
    """
    if not project_id:
        raise ValueError("Invalid project ID.")

    result = await models.Project.where(id=project_id).update(set={"name": name})
    return bool(result.affected_rows)  # type: ignore


@register_api("projects.set_project_description")
async def set_project_description(project_id: str, description: str) -> str:
    """
    Update a project's description

    Args:
        - project_id (str): the project ID
        - description (str): the description to give the provided project

    Returns:
        - str: the project ID

    Raises:
        - ValueError: if the project doesn't exist
    """
    if not project_id:
        raise ValueError("Invalid project ID.")

    result = await models.Project.where(id=project_id).update(
        set={"description": description}
    )
    return bool(result.affected_rows)  # type: ignore


@register_api("projects.delete_project")
async def delete_project(project_id: str) -> bool:
    """
    Deletes a project.

    Args:
        - project_id (str): the project to delete

    Returns:
        - bool: if the delete succeeded

    Raises:
        - ValueError: if an ID isn't provided
    """
    if not project_id:
        raise ValueError("Invalid project ID.")

    result = await models.Project.where(id=project_id).delete()
    return bool(result.affected_rows)  # type: ignore
