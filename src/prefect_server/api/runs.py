import datetime
from typing import Any, Iterable, List, Optional

import pendulum

import prefect
from prefect import api, models
from prefect.engine.state import Pending, Queued, Scheduled
from prefect.utilities.graphql import EnumValue
from prefect.utilities.plugins import register_api
from prefect_server import config
from prefect_server.utilities import exceptions, names

SCHEDULED_STATES = [
    s.__name__
    for s in prefect.engine.state.__dict__.values()
    if isinstance(s, type) and issubclass(s, (Scheduled, Queued))
]


@register_api("runs.create_flow_run")
async def create_flow_run(
    flow_id: Optional[str] = None,
    parameters: Optional[dict] = None,
    context: Optional[dict] = None,
    scheduled_start_time: datetime.datetime = None,
    flow_run_name: Optional[str] = None,
    version_group_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    labels: List[str] = None,
    run_config: Optional[dict] = None,
) -> Any:
    """
    Creates a new flow run for an existing flow.

    Args:
        - flow_id (str): A string representing the current flow id
        - parameters (dict, optional): A dictionary of parameters that were specified for the flow
        - context (dict, optional): A dictionary of context values
        - scheduled_start_time (datetime.datetime): When the flow_run should be scheduled to run. If `None`,
            defaults to right now. Must be UTC.
        - flow_run_name (str, optional): An optional string representing this flow run
        - version_group_id (str, optional): An optional version group ID; if provided, will run the most
            recent unarchived version of the group
        - idempotency_key (str, optional): An optional idempotency key to prevent duplicate run creation.
            Idempotency keys are only respected for 24 hours after a flow is created.
        - labels (List[str], optional): a list of labels to apply to this individual flow run
        - run-config (dict, optional): A run-config override for this flow run.
    """

    if idempotency_key is not None:

        where = {
            "idempotency_key": {"_eq": idempotency_key},
        }
        if flow_id is not None:
            where.update({"flow_id": {"_eq": flow_id}})
        if version_group_id is not None:
            where.update({"flow": {"version_group_id": {"_eq": version_group_id}}})
        run = await models.FlowRun.where(where).first(
            {"id"}, order_by={"created": EnumValue("desc")}
        )
        if run is not None:
            return run.id

    flow_run_id = await _create_flow_run(
        flow_id=flow_id,
        parameters=parameters,
        context=context,
        scheduled_start_time=scheduled_start_time,
        flow_run_name=flow_run_name,
        version_group_id=version_group_id,
        labels=labels,
        run_config=run_config,
    )

    if idempotency_key is not None:
        await models.FlowRun.where(id=flow_run_id).update(
            {"idempotency_key": idempotency_key}
        )

    return flow_run_id


@register_api("runs.set_flow_run_labels")
async def set_flow_run_labels(flow_run_id: str, labels: List[str]) -> bool:
    if flow_run_id is None:
        raise ValueError("Invalid flow run ID")
    elif labels is None:
        raise ValueError("Invalid labels")
    result = await models.FlowRun.where(id=flow_run_id).update(
        {"labels": sorted(labels)}
    )
    return bool(result.affected_rows)


@register_api("runs.set_flow_run_name")
async def set_flow_run_name(flow_run_id: str, name: str) -> bool:
    if flow_run_id is None:
        raise ValueError("Invalid flow run ID")
    elif not name:
        raise ValueError("Invalid name")
    result = await models.FlowRun.where(id=flow_run_id).update({"name": name})
    return bool(result.affected_rows)


@register_api("runs.set_task_run_name")
async def set_task_run_name(task_run_id: str, name: str) -> bool:
    if task_run_id is None:
        raise ValueError("Invalid task run ID")
    elif not name:
        raise ValueError("Invalid name")
    result = await models.TaskRun.where(id=task_run_id).update({"name": name})
    return bool(result.affected_rows)


@register_api("runs._create_flow_run")
async def _create_flow_run(
    flow_id: Optional[str] = None,
    parameters: Optional[dict] = None,
    context: Optional[dict] = None,
    scheduled_start_time: datetime.datetime = None,
    flow_run_name: Optional[str] = None,
    version_group_id: Optional[str] = None,
    labels: List[str] = None,
    run_config: Optional[dict] = None,
) -> Any:
    """
    Creates a new flow run for an existing flow.

    Args:
        - flow_id (str): A string representing the current flow id
        - parameters (dict, optional): A dictionary of parameters that were specified for the flow
        - context (dict, optional): A dictionary of context values
        - scheduled_start_time (datetime.datetime): When the flow_run should be scheduled to run. If `None`,
            defaults to right now. Must be UTC.
        - flow_run_name (str, optional): An optional string representing this flow run
        - version_group_id (str, optional): An optional version group ID; if provided, will run the most
            recent unarchived version of the group
        - labels (List[str], optional): a list of labels to apply to this individual flow run
        - run-config (dict, optional): A run-config override for this flow run.
    """

    if flow_id is None and version_group_id is None:
        raise ValueError("One of flow_id or version_group_id must be provided.")

    scheduled_start_time = scheduled_start_time or pendulum.now()

    if flow_id:
        where_clause = {"id": {"_eq": flow_id}}
    elif version_group_id:
        where_clause = {
            "version_group_id": {"_eq": version_group_id},
            "archived": {"_eq": False},
        }

    flow = await models.Flow.where(where=where_clause).first(
        {
            "id": True,
            "archived": True,
            "tenant_id": True,
            "environment": True,
            "run_config": True,
            "parameters": True,
            "flow_group_id": True,
            "flow_group": {
                "default_parameters": True,
                "labels": True,
                "run_config": True,
            },
        },
        order_by={"version": EnumValue("desc")},
    )  # type: Any

    if not flow:
        msg = (
            f"Flow {flow_id} not found"
            if flow_id
            else f"Version group {version_group_id} has no unarchived flows."
        )
        raise exceptions.NotFound(msg)
    elif flow.archived:
        raise ValueError(f"Flow {flow.id} is archived.")

    # determine active labels
    if labels is not None:
        run_labels = labels
    elif run_config is not None:
        run_labels = run_config.get("labels") or []
    elif flow.flow_group.labels is not None:
        run_labels = flow.flow_group.labels
    elif flow.flow_group.run_config is not None:
        run_labels = flow.flow_group.run_config.get("labels") or []
    elif flow.run_config is not None:
        run_labels = flow.run_config.get("labels") or []
    elif flow.environment is not None:
        run_labels = flow.environment.get("labels") or []
    else:
        run_labels = []
    run_labels.sort()

    # determine active run_config
    if run_config is None:
        if flow.flow_group.run_config is not None:
            run_config = flow.flow_group.run_config
        else:
            run_config = flow.run_config

    # check parameters
    run_parameters = flow.flow_group.default_parameters
    run_parameters.update((parameters or {}))
    required_parameters = [p["name"] for p in flow.parameters if p["required"]]
    missing = set(required_parameters).difference(run_parameters)
    if missing:
        raise ValueError(f"Required parameters were not supplied: {missing}")
    state = Scheduled(message="Flow run scheduled.", start_time=scheduled_start_time)

    run = models.FlowRun(
        tenant_id=flow.tenant_id,
        flow_id=flow_id or flow.id,
        labels=run_labels,
        parameters=run_parameters,
        run_config=run_config,
        context=context or {},
        scheduled_start_time=scheduled_start_time,
        name=flow_run_name or names.generate_slug(2),
        states=[
            models.FlowRunState(
                tenant_id=flow.tenant_id,
                **models.FlowRunState.fields_from_state(
                    Pending(message="Flow run created")
                ),
            )
        ],
    )

    flow_run_id = await run.insert()

    # apply the flow run's initial state via `set_flow_run_state`
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=state)

    return flow_run_id


@register_api("runs.get_or_create_task_run")
async def get_or_create_task_run(
    flow_run_id: str, task_id: str, map_index: int = None
) -> str:
    """
    Since some task runs are created dynamically (when tasks are mapped, for example)
    we don't know if a task run exists the first time we query it. This function will take
    key information about a task run and create it if it doesn't already exist, returning its id.
    """

    if map_index is None:
        map_index = -1

    # try to load an existing task run
    task_run = await models.TaskRun.where(
        {
            "flow_run_id": {"_eq": flow_run_id},
            "task_id": {"_eq": task_id},
            "map_index": {"_eq": map_index},
        }
    ).first({"id"})

    if task_run:
        return task_run.id

    try:
        # load the tenant ID and cache_key
        task = await models.Task.where(id=task_id).first({"cache_key", "tenant_id"})
        # create the task run
        return await models.TaskRun(
            tenant_id=task.tenant_id,
            flow_run_id=flow_run_id,
            task_id=task_id,
            map_index=map_index,
            cache_key=task.cache_key,
            states=[
                models.TaskRunState(
                    tenant_id=task.tenant_id,
                    **models.TaskRunState.fields_from_state(
                        Pending(message="Task run created")
                    ),
                )
            ],
        ).insert()

    except Exception:
        raise ValueError("Invalid ID")


@register_api("runs.get_or_create_task_run_info")
async def get_or_create_task_run_info(
    flow_run_id: str, task_id: str, map_index: int = None
) -> dict:
    """
    Given a flow_run_id, task_id, and map_index, return details about the corresponding task run.
    If the task run doesn't exist, it will be created.

    Returns:
        - dict: a dict of details about the task run, including its id, version, and state.
    """

    if map_index is None:
        map_index = -1

    task_run = await models.TaskRun.where(
        {
            "flow_run_id": {"_eq": flow_run_id},
            "task_id": {"_eq": task_id},
            "map_index": {"_eq": map_index},
        }
    ).first({"id", "version", "state", "serialized_state"})

    if task_run:
        return dict(
            id=task_run.id,
            version=task_run.version,
            state=task_run.state,
            serialized_state=task_run.serialized_state,
        )

    # if it isn't found, add it to the DB
    task = await models.Task.where(id=task_id).first({"cache_key", "tenant_id"})
    if not task:
        raise ValueError("Invalid task ID")

    db_task_run = models.TaskRun(
        tenant_id=task.tenant_id,
        flow_run_id=flow_run_id,
        task_id=task_id,
        map_index=map_index,
        cache_key=task.cache_key,
        version=0,
    )

    db_task_run_state = models.TaskRunState(
        tenant_id=task.tenant_id,
        state="Pending",
        timestamp=pendulum.now(),
        message="Task run created",
        serialized_state=Pending(message="Task run created").serialize(),
    )

    db_task_run.states = [db_task_run_state]
    run = await db_task_run.insert(
        on_conflict=dict(
            constraint="task_run_unique_identifier_key",
            update_columns=["cache_key"],
        ),
        selection_set={"returning": {"id"}},
    )

    return dict(
        id=run.returning.id,
        version=db_task_run.version,
        state="Pending",
        serialized_state=db_task_run_state.serialized_state,
    )


@register_api("runs.update_flow_run_heartbeat")
async def update_flow_run_heartbeat(
    flow_run_id: str,
) -> None:
    """
    Updates the heartbeat of a flow run.

    Args:
        - flow_run_id (str): the flow run id

    Raises:
        - ValueError: if the flow_run_id is invalid
    """

    result = await models.FlowRun.where(id=flow_run_id).update(
        set={"heartbeat": pendulum.now("utc")}
    )
    if not result.affected_rows:
        raise ValueError("Invalid flow run ID")


@register_api("runs.update_task_run_heartbeat")
async def update_task_run_heartbeat(
    task_run_id: str,
) -> None:
    """
    Updates the heartbeat of a task run. Also sets the corresponding flow run heartbeat.

    Args:
        - task_run_id (str): the task run id

    Raises:
        - ValueError: if the task_run_id is invalid
    """
    result = await models.TaskRun.where(id=task_run_id).update(
        set={"heartbeat": pendulum.now("utc")}
    )
    if not result.affected_rows:
        raise ValueError("Invalid task run ID")


@register_api("runs.delete_flow_run")
async def delete_flow_run(flow_run_id: str) -> bool:
    """
    Deletes a flow run.

    Args:
        - flow_run_id (str): the flow run to delete

    Returns:
        - bool: if the delete succeeded

    Raises:
        - ValueError: if an ID isn't provided
    """
    if not flow_run_id:
        raise ValueError("Invalid flow run ID.")

    result = await models.FlowRun.where(id=flow_run_id).delete()
    return bool(result.affected_rows)  # type: ignore


@register_api("runs.update_flow_run_agent")
async def update_flow_run_agent(flow_run_id: str, agent_id: str) -> bool:
    """
    Updates the agent instance of a flow run

    Args:
        - flow_run_id (str): the flow run id
        - agent_id (str): the id of an agent instance submitting the flow run

    Returns:
        bool: if the update was successful
    """

    agent = await models.Agent.where(id=agent_id).first()
    if not agent:
        return False

    result = await models.FlowRun.where(id=flow_run_id).update(
        set={"agent_id": agent_id}
    )
    return bool(result.affected_rows)


@register_api("runs.get_runs_in_queue")
async def get_runs_in_queue(
    tenant_id: str,
    before: datetime = None,
    labels: Iterable[str] = None,
    agent_id: Optional[str] = None,
) -> List[str]:

    if tenant_id is None:
        raise ValueError("Invalid tenant ID")

    if before is None:
        before = pendulum.now("UTC")

    labels = labels or []

    flow_runs = await models.FlowRun.where(
        {
            "tenant_id": {"_eq": tenant_id},
            # EITHER
            "_or": [
                # The flow run is scheduled
                {
                    "state": {"_in": SCHEDULED_STATES},
                    "state_start_time": {"_lte": str(before)},
                },
                # one of the flow run's task runs is scheduled
                # and the flow run is running
                {
                    "state": {"_eq": "Running"},
                    "task_runs": {
                        "state": {"_in": SCHEDULED_STATES},
                        "state_start_time": {"_lte": str(before)},
                    },
                },
            ],
        }
    ).get(
        {
            "id": True,
            "labels": True,
        },
        order_by=[{"state_start_time": EnumValue("asc")}],
        # get extra in case labeled runs don't show up at the top
        limit=config.queued_runs_returned_limit * 3,
    )

    counter = 0
    final_flow_runs = []

    for flow_run in flow_runs:
        if counter == config.queued_runs_returned_limit:
            continue

        run_labels = flow_run.labels

        # if the run labels are a superset of the provided labels, skip
        if set(run_labels) - set(labels):
            continue

        # if the run has no labels but labels were provided, skip
        if not run_labels and labels:
            continue

        final_flow_runs.append(flow_run.id)
        counter += 1

    if agent_id:
        await api.agents.update_agent_last_queried(agent_id=agent_id)

    return final_flow_runs
