import datetime
from typing import Any, Iterable, List

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
    flow_id: str = None,
    parameters: dict = None,
    context: dict = None,
    scheduled_start_time: datetime.datetime = None,
    flow_run_name: str = None,
    version_group_id: str = None,
    idempotency_key: str = None,
    labels: List[str] = None,
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
    """

    if idempotency_key is not None:

        where = {
            "idempotency_key": {"_eq": idempotency_key},
            "created": {"_gt": str(pendulum.now().subtract(days=1))},
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
    flow_id: str = None,
    parameters: dict = None,
    context: dict = None,
    scheduled_start_time: datetime.datetime = None,
    flow_run_name: str = None,
    version_group_id: str = None,
    labels: List[str] = None,
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
            "flow_group": {"default_parameters": True, "labels": True},
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

    # set labels
    if labels is not None:
        run_labels = labels
    elif flow.flow_group.labels is not None:
        run_labels = flow.flow_group.labels
    elif flow.run_config is not None:
        run_labels = flow.run_config.get("labels") or []
    else:
        run_labels = flow.environment.get("labels") or []
    run_labels.sort()

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


@register_api("runs.get_or_create_mapped_task_run_children")
async def get_or_create_mapped_task_run_children(
    flow_run_id: str, task_id: str, max_map_index: int
) -> List[str]:
    """
    Creates and/or retrieves mapped child task runs for a given flow run and task.

    Args:
        - flow_run_id (str): the flow run associated with the parent task run
        - task_id (str): the task ID to create and/or retrieve
        - max_map_index (int,): the number of mapped children e.g., a value of 2 yields 3 mapped children
    """
    # grab task info
    task = await models.Task.where(id=task_id).first({"cache_key", "tenant_id"})
    # generate task runs to upsert
    task_runs = [
        models.TaskRun(
            tenant_id=task.tenant_id,
            flow_run_id=flow_run_id,
            task_id=task_id,
            map_index=i,
            cache_key=task.cache_key,
        )
        for i in range(max_map_index + 1)
    ]
    # upsert the mapped children
    task_runs = (
        await models.TaskRun().insert_many(
            objects=task_runs,
            on_conflict=dict(
                constraint="task_run_unique_identifier_key",
                update_columns=["cache_key"],
            ),
            selection_set={"returning": {"id", "map_index"}},
        )
    )["returning"]
    task_runs.sort(key=lambda task_run: task_run.map_index)
    # get task runs without states
    stateless_runs = await models.TaskRun.where(
        {
            "flow_run_id": {"_eq": flow_run_id},
            "task_id": {"_eq": task_id},
            # this syntax indicates "where there are no states"
            "_not": {"states": {}},
        }
    ).get({"id", "map_index", "version"})
    # create and insert states for stateless task runs
    task_run_states = [
        models.TaskRunState(
            tenant_id=task.tenant_id,
            task_run_id=task_run.id,
            **models.TaskRunState.fields_from_state(
                Pending(message="Task run created")
            ),
        )
        for task_run in stateless_runs
    ]
    await models.TaskRunState().insert_many(task_run_states)

    # return the task run ids
    return [task_run.id for task_run in task_runs]


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
    agent_id: str = None,
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
            "flow": {
                "environment": True,
                "run_config": True,
                "flow_group": {"labels": True},
            },
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
