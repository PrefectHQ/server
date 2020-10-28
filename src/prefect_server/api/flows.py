import datetime
import hashlib
import json
import uuid
from typing import Any, Dict, List

import pendulum
from packaging import version as module_version
from pydantic import BaseModel, Field, validator

from prefect import api, models
from prefect.serialization.schedule import ScheduleSchema
from prefect.utilities.graphql import with_args, EnumValue
from prefect.utilities.plugins import register_api
from prefect_server import config
from prefect_server.utilities import logging

logger = logging.get_logger("api.flows")
schedule_schema = ScheduleSchema()

# -----------------------------------------------------
# Schema for deserializing flows
# -----------------------------------------------------


class Model(BaseModel):
    class Config:
        # allow extra fields in case schema changes
        extra = "allow"


class ClockSchema(Model):
    parameter_defaults: Dict = Field(default_factory=dict)
    labels: List[str] = Field(default=None)


class ScheduleSchema(Model):
    clocks: List[ClockSchema] = Field(default_factory=list)


class TaskSchema(Model):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = None
    slug: str
    type: str = None
    auto_generated: bool = False
    tags: List[str] = Field(default_factory=list)
    max_retries: int = 0
    retry_delay: datetime.timedelta = None
    cache_key: str = None
    trigger: str = None
    mapped: bool = False
    is_reference_task: bool = False
    is_root_task: bool = False
    is_terminal_task: bool = False

    @validator("trigger", pre=True)
    def _validate_trigger(cls, v):
        # core sends the trigger as an abbreviated dictionary
        if isinstance(v, dict):
            return v.get("fn")
        return v


class EdgeSchema(Model):
    upstream_task: str
    downstream_task: str
    mapped: bool = False
    key: str = None

    @validator("upstream_task", pre=True)
    def _validate_upstream_task(cls, v):
        # core sends the task as an abbreviated dictionary
        if isinstance(v, dict):
            return v.get("slug")
        return v

    @validator("downstream_task", pre=True)
    def _validate_downstream_task(cls, v):
        # core sends the task as an abbreviated dictionary
        if isinstance(v, dict):
            return v.get("slug")
        return v


class ParameterSchema(Model):
    name: str = None
    slug: str
    required: bool = False
    default: Any = None


class FlowSchema(Model):
    name: str = None
    tasks: List[TaskSchema] = Field(default_factory=list)
    edges: List[EdgeSchema] = Field(default_factory=list)
    parameters: List[ParameterSchema] = Field(default_factory=list)
    environment: Dict[str, Any] = None
    run_config: Dict[str, Any] = None
    __version__: str = None
    storage: Dict[str, Any] = None
    schedule: ScheduleSchema = None
    reference_tasks: List[str] = Field(default_factory=list)

    @validator("reference_tasks", pre=True)
    def _validate_reference_tasks(cls, v):
        reference_tasks = []
        for t in v:
            # core sends the task as an abbreviated dictionary
            if isinstance(t, dict):
                t = t.get("slug")
            reference_tasks.append(t)
        return reference_tasks


@register_api("flows.create_flow")
async def create_flow(
    serialized_flow: dict,
    project_id: str,
    version_group_id: str = None,
    set_schedule_active: bool = True,
    description: str = None,
    idempotency_key: str = None,
) -> str:
    """
    Add a flow to the database.

    Args:
        - project_id (str): A project id
        - serialized_flow (dict): A dictionary of information used to represent a flow
        - version_group_id (str): A version group to add the Flow to
        - set_schedule_active (bool): Whether to set the flow's schedule to active
        - description (str): a description of the flow being created
        - idempotency_key (optional, str): a key that, if matching the most recent call
            to `create_flow` for this flow group, will prevent the creation of another
            flow version

    Returns:
        str: The id of the new flow

    Raises:
        - ValueError: if the flow's version of Prefect Core falls below the cutoff

    """
    flow = FlowSchema(**serialized_flow)

    # core versions before 0.6.1 were used only for internal purposes-- this is our cutoff
    core_version = flow.__version__
    if core_version and module_version.parse(core_version) < module_version.parse(
        config.core_version_cutoff
    ):
        raise ValueError(
            "Prefect backends require new flows to be built with Prefect "
            f"{config.core_version_cutoff}+, but this flow was built with "
            f"Prefect {core_version}."
        )

    # load project
    project = await models.Project.where(id=project_id).first({"tenant_id"})
    if not project:
        raise ValueError("Invalid project.")
    tenant_id = project.tenant_id  # type: ignore

    # set up task detail info
    task_lookup = {t.slug: t for t in flow.tasks}
    tasks_with_upstreams = {e.downstream_task for e in flow.edges}
    tasks_with_downstreams = {e.upstream_task for e in flow.edges}
    reference_tasks = set(flow.reference_tasks) or {
        t.slug for t in flow.tasks if t.slug not in tasks_with_downstreams
    }

    for t in flow.tasks:
        t.mapped = any(e.mapped for e in flow.edges if e.downstream_task == t.slug)
        t.is_reference_task = t.slug in reference_tasks
        t.is_root_task = t.slug not in tasks_with_upstreams
        t.is_terminal_task = t.slug not in tasks_with_downstreams

    # set up versioning
    version_group_id = version_group_id or str(uuid.uuid4())
    version_where = {
        "version_group_id": {"_eq": version_group_id},
        "tenant_id": {"_eq": tenant_id},
    }

    # lookup the associated flow group (may not exist yet)
    flow_group = await models.FlowGroup.where(
        {
            "_and": [
                {"tenant_id": {"_eq": tenant_id}},
                {"name": {"_eq": version_group_id}},
            ]
        }
    ).first({"id", "schedule", "settings"})

    # create the flow group or check for the idempotency key in the existing flow group
    # settings
    if flow_group is None:
        flow_group_id = await models.FlowGroup(
            tenant_id=tenant_id,
            name=version_group_id,
            settings={
                "heartbeat_enabled": True,
                "lazarus_enabled": True,
                "version_locking_enabled": False,
                "idempotency_key": idempotency_key,
            },
        ).insert()
    else:
        flow_group_id = flow_group.id

        # check idempotency key and exit early if we find a matching key and flow,
        # otherwise update the key for the group
        last_idempotency_key = flow_group.settings.get("idempotency_key", None)
        if (
            last_idempotency_key
            and idempotency_key
            and last_idempotency_key == idempotency_key
        ):
            # get the most recent unarchived version, there should only be one
            # unarchived flow at a time but it is safer not to presume
            flow_model = await models.Flow.where(
                {
                    "version_group_id": {"_eq": version_group_id},
                    "archived": {"_eq": False},
                }
            ).first(order_by={"version": EnumValue("desc")})
            if flow_model:
                return flow_model.id
            # otherwise, despite the key matching we don't have a valid flow to return
            # and will continue as though the key did not match

        settings = flow_group.settings
        settings["idempotency_key"] = idempotency_key
        await models.FlowGroup.where({"id": {"_eq": flow_group.id}}).update(
            set={"settings": settings}
        )

    version = (await models.Flow.where(version_where).max({"version"}))["version"] or 0

    # if there is no referenceable schedule for this Flow,
    # we should set its "schedule" to inactive to avoid confusion
    if flow.schedule is None and getattr(flow_group, "schedule", None) is None:
        set_schedule_active = False

    # precompute task ids to make edges easy to add to database
    flow_id = await models.Flow(
        tenant_id=tenant_id,
        project_id=project_id,
        name=flow.name,
        serialized_flow=serialized_flow,
        environment=flow.environment,
        run_config=flow.run_config,
        core_version=flow.__version__,
        storage=flow.storage,
        parameters=flow.parameters,
        version_group_id=version_group_id,
        version=version + 1,
        archived=False,
        flow_group_id=flow_group_id,
        description=description,
        schedule=serialized_flow.get("schedule"),
        is_schedule_active=False,
        tasks=[
            models.Task(
                id=t.id,
                tenant_id=tenant_id,
                name=t.name,
                slug=t.slug,
                type=t.type,
                max_retries=t.max_retries,
                tags=t.tags,
                retry_delay=t.retry_delay,
                trigger=t.trigger,
                mapped=t.mapped,
                auto_generated=t.auto_generated,
                cache_key=t.cache_key,
                is_reference_task=t.is_reference_task,
                is_root_task=t.is_root_task,
                is_terminal_task=t.is_terminal_task,
            )
            for t in flow.tasks
        ],
        edges=[
            models.Edge(
                tenant_id=tenant_id,
                upstream_task_id=task_lookup[e.upstream_task].id,
                downstream_task_id=task_lookup[e.downstream_task].id,
                key=e.key,
                mapped=e.mapped,
            )
            for e in flow.edges
        ],
    ).insert()

    # schedule runs
    if set_schedule_active:
        # we don't want to error the Flow creation call as it would prevent other archiving logic
        # from kicking in
        try:
            await api.flows.set_schedule_active(flow_id=flow_id)
        except ValueError:
            pass

    return flow_id


@register_api("flows.delete_flow")
async def delete_flow(flow_id: str) -> bool:
    """
    Deletes a flow.

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the delete succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    # delete the flow
    result = await models.Flow.where(id=flow_id).delete()
    return bool(result.affected_rows)


@register_api("flows.archive_flow")
async def archive_flow(flow_id: str) -> bool:
    """
    Archives a flow.

    Archiving a flow prevents it from scheduling new runs. It also:
        - deletes any currently scheduled runs
        - resets the "last scheduled run time" of any schedules

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    result = await models.Flow.where({"id": {"_eq": flow_id}}).update(
        set={"archived": True}
    )
    if not result.affected_rows:
        return False

    # delete scheduled flow runs
    await models.FlowRun.where(
        {"flow_id": {"_eq": flow_id}, "state": {"_eq": "Scheduled"}}
    ).delete()

    return True


@register_api("flows.unarchive_flow")
async def unarchive_flow(flow_id: str) -> bool:
    """
    Unarchives a flow.

    Args:
        - flow_id (str): the flow id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if a flow ID is not provided
    """
    if not flow_id:
        raise ValueError("Must provide flow ID.")

    result = await models.Flow.where({"id": {"_eq": flow_id}}).update(
        set={"archived": False},
        selection_set={"affected_rows": True, "returning": {"is_schedule_active"}},
    )

    # if the schedule is active, jog it to trigger scheduling
    if result.affected_rows and result.returning[0].is_schedule_active:
        await set_schedule_active(flow_id)

    return bool(result.affected_rows)  # type: ignore


@register_api("flows.update_flow_project")
async def update_flow_project(flow_id: str, project_id: str) -> bool:
    """
    Updates a flow's project.

    Args:
        - flow_id (str): the flow id
        - project_id (str): the new project id

    Returns:
        - bool: if the update succeeded

    Raises:
        - ValueError: if flow or project IDs are not provided
    """
    if flow_id is None:
        raise ValueError("Invalid flow ID.")
    if project_id is None:
        raise ValueError("Invalid project ID.")

    result = await models.Flow.where(
        {"id": {"_eq": flow_id}, "tenant": {"projects": {"id": {"_eq": project_id}}}}
    ).update(dict(project_id=project_id))
    if not bool(result.affected_rows):
        raise ValueError("Invalid flow or project ID.")
    return flow_id


@register_api("flows.set_schedule_active")
async def set_schedule_active(flow_id: str) -> bool:
    """
    Sets a flow schedule to active

    Args:
        - flow_id (str): the flow ID

    Returns:
        bool: if the update succeeded
    """
    if flow_id is None:
        raise ValueError("Invalid flow id.")

    flow = await models.Flow.where(id=flow_id).first(
        {
            "schedule": True,
            "parameters": True,
            "flow_group": {"schedule": True, "default_parameters": True},
        }
    )

    if not flow:
        return False

    # logic for determining if it's appropriate to turn on the schedule for this flow
    # we can set a flow run schedule to active if any required parameters are provided by:
    # - the Flow's own clocks
    # - the Flow Group's default parameters
    # - some combination of the above two
    required_parameters = {p.get("name") for p in flow.parameters if p.get("required")}
    if flow.schedule is not None and required_parameters:
        required_names = required_parameters.difference(
            flow.flow_group.default_parameters or {}
        )
        clock_params = [
            set(c.get("parameter_defaults", {}).keys())
            for c in flow.schedule.get("clocks", [])
        ]
        if not all([required_names <= c for c in clock_params]):
            raise ValueError("Can not schedule a flow that has required parameters.")

    result = await models.Flow.where(id=flow_id).update(
        set={"is_schedule_active": True}
    )
    if not result.affected_rows:
        return False

    await api.flows.schedule_flow_runs(flow_id=flow_id)
    return True


@register_api("flows.set_schedule_inactive")
async def set_schedule_inactive(flow_id: str) -> bool:
    """
    Sets a flow schedule to inactive

    Args:
        - flow_id (str): the flow ID

    Returns:
        bool: if the update succeeded
    """
    if flow_id is None:
        raise ValueError("Invalid flow id.")

    result = await models.Flow.where(id=flow_id).update(
        set={"is_schedule_active": False}
    )
    if not result.affected_rows:
        return False

    deleted_runs = await models.FlowRun.where(
        {
            "flow_id": {"_eq": flow_id},
            "state": {"_eq": "Scheduled"},
            "auto_scheduled": {"_eq": True},
        }
    ).delete()

    return True


@register_api("flows.schedule_flow_runs")
async def schedule_flow_runs(flow_id: str, max_runs: int = None) -> List[str]:
    """
    Schedule the next `max_runs` runs for this flow. Runs will not be scheduled
    if they are earlier than latest currently-scheduled run that has auto_scheduled = True.

    Runs are created with an idempotency key to avoid rescheduling.

    Args:
        - flow_id (str): the flow ID
        - max_runs (int): the maximum number of runs to schedule (defaults to 10)

    Returns:
        - List[str]: the ids of the new runs
    """

    if max_runs is None:
        max_runs = 10

    if flow_id is None:
        raise ValueError("Invalid flow id.")

    run_ids = []

    flow = await models.Flow.where(
        {
            # match the provided ID
            "id": {"_eq": flow_id},
            # schedule is not none or flow group schedule is not none
            "_or": [
                {"schedule": {"_is_null": False}},
                {"flow_group": {"schedule": {"_is_null": False}}},
            ],
            # schedule is active
            "is_schedule_active": {"_eq": True},
            # flow is not archived
            "archived": {"_eq": False},
        }
    ).first(
        {
            "schedule": True,
            "flow_group": {"schedule": True},
            with_args(
                "flow_runs_aggregate", {"where": {"auto_scheduled": {"_eq": True}}}
            ): {"aggregate": {"max": "scheduled_start_time"}},
        },
        apply_schema=False,
    )

    if not flow:
        logger.debug(f"Flow {flow_id} can not be scheduled.")
        return run_ids
    else:
        # attempt to pull the schedule from the flow group if possible
        if flow.flow_group.schedule:
            flow_schedule = flow.flow_group.schedule
        # if not possible, pull the schedule from the flow
        else:
            flow_schedule = flow.schedule
        try:
            flow_schedule = schedule_schema.load(flow_schedule)
        except Exception as exc:
            logger.error(exc)
            logger.critical(
                f"Failed to deserialize schedule for flow {flow_id}: {flow_schedule}"
            )
            return run_ids

    if flow.flow_runs_aggregate.aggregate.max.scheduled_start_time is not None:
        last_scheduled_run = pendulum.parse(
            flow.flow_runs_aggregate.aggregate.max.scheduled_start_time
        )
    else:
        last_scheduled_run = pendulum.now("UTC")

    # schedule every event with an idempotent flow run
    for event in flow_schedule.next(n=max_runs, return_events=True):

        # if the event has parameter defaults or labels, we do allow for
        # same-time scheduling
        if event.parameter_defaults or event.labels is not None:
            md5 = hashlib.md5()
            param_string = str(sorted(json.dumps(event.parameter_defaults)))
            label_string = str(sorted(json.dumps(event.labels)))
            md5.update((param_string + label_string).encode("utf-8"))
            idempotency_key = (
                f"auto-scheduled:{event.start_time.in_tz('UTC')}:{md5.hexdigest()}"
            )
        # if this run was already scheduled, continue
        elif last_scheduled_run and event.start_time <= last_scheduled_run:
            continue
        else:
            idempotency_key = f"auto-scheduled:{event.start_time.in_tz('UTC')}"

        run_id = await api.runs.create_flow_run(
            flow_id=flow_id,
            scheduled_start_time=event.start_time,
            parameters=event.parameter_defaults,
            labels=event.labels,
            idempotency_key=idempotency_key,
        )

        logger.debug(
            f"Flow run {run_id} of flow {flow_id} scheduled for {event.start_time}"
        )

        run_ids.append(run_id)

    await models.FlowRun.where({"id": {"_in": run_ids}}).update(
        set={"auto_scheduled": True}
    )

    return run_ids
