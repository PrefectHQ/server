import datetime

import pendulum
import pytest

import prefect
from prefect import api, models
from prefect.engine.state import Running, Submitted, Success
from prefect_server import config

START_TIME = pendulum.now()


@pytest.fixture(autouse=True)
async def clear_database():
    try:
        yield
    finally:
        await models.Tenant.where({"created": {"_gt": str(START_TIME)}}).delete()


@pytest.fixture
async def tenant_id():
    return await api.tenants.create_tenant(name="Test Tenant")


@pytest.fixture
async def agent_id(tenant_id):
    return await api.agents.register_agent(tenant_id=tenant_id, labels=["foo", "bar"])


@pytest.fixture
async def project_id(tenant_id):
    project_id = await api.projects.create_project(
        tenant_id=tenant_id, name="Test Project"
    )
    return project_id


@pytest.fixture
async def project_id_2(tenant_id):
    project_id_2 = await api.projects.create_project(
        tenant_id=tenant_id, name="Test Project 2"
    )
    return project_id_2


@pytest.fixture
async def flow_id(project_id):
    flow = prefect.Flow(
        name="Test Flow",
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))

    flow_id = await api.flows.create_flow(
        project_id=project_id, serialized_flow=flow.serialize()
    )

    return flow_id


@pytest.fixture
async def flow_group_id(flow_id):
    flow = await models.Flow.where(id=flow_id).first({"flow_group_id"})
    return flow.flow_group_id


@pytest.fixture
async def labeled_flow_id(project_id):
    flow = prefect.Flow(
        name="Labeled Flow",
        environment=prefect.environments.execution.local.LocalEnvironment(
            labels=["foo", "bar"]
        ),
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))

    flow_id = await api.flows.create_flow(
        project_id=project_id, serialized_flow=flow.serialize()
    )
    return flow_id


@pytest.fixture
async def task_id(flow_id):
    task = await models.Task.where({"flow_id": {"_eq": flow_id}}).first("id")
    return task.id


@pytest.fixture
async def labeled_task_id(labeled_flow_id):
    task = await models.Task.where({"flow_id": {"_eq": labeled_flow_id}}).first("id")
    return task.id


@pytest.fixture
async def parameter_id(flow_id):
    task = await models.Task.where(
        {"flow_id": {"_eq": flow_id}, "type": {"_like": "%Parameter%"}}
    ).first("id")
    return task.id


@pytest.fixture
async def edge_id(flow_id):
    edge = await models.Edge.where({"flow_id": {"_eq": flow_id}}).first("id")
    return edge.id


@pytest.fixture
async def flow_run_id(flow_id):
    return await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))


@pytest.fixture
async def running_flow_run_id(flow_run_id):
    """
    Sets the `flow_run_id` fixture to be running, which makes it easier to
    put task runs into a running state
    """
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
    return flow_run_id


@pytest.fixture
async def labeled_flow_run_id(labeled_flow_id):
    return await api.runs.create_flow_run(flow_id=labeled_flow_id, parameters=dict(x=1))


@pytest.fixture
async def flow_run_id_2(flow_id):
    """
    A flow run in a Running state
    """

    flow_run_id = await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
    return flow_run_id


@pytest.fixture
async def flow_run_id_3(flow_id):
    """
    A flow run in a Success state
    """
    flow_run_id = await api.runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Running())
    await api.states.set_flow_run_state(flow_run_id=flow_run_id, state=Success())
    return flow_run_id


@pytest.fixture
async def task_run_id(flow_run_id, task_id):
    return await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id, task_id=task_id, map_index=None
    )


@pytest.fixture
async def labeled_task_run_id(labeled_flow_run_id, labeled_task_id):
    return await api.runs.get_or_create_task_run(
        flow_run_id=labeled_flow_run_id, task_id=labeled_task_id, map_index=None
    )


@pytest.fixture
async def task_run_id_2(flow_run_id_2, task_id):
    """
    A task run in a Running state
    """

    task_run_id = await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id_2, task_id=task_id, map_index=None
    )
    await api.states.set_task_run_state(task_run_id=task_run_id, state=Running())
    return task_run_id


@pytest.fixture
async def task_run_id_3(flow_run_id_3, task_id):
    """
    A task run in a Success state
    """
    task_run_id = await api.runs.get_or_create_task_run(
        flow_run_id=flow_run_id_3, task_id=task_id, map_index=None
    )

    # start at version 1 because the flow run finished and incremented all versions
    await api.states.set_task_run_state(task_run_id=task_run_id, state=Success())
    return task_run_id


@pytest.fixture
async def excess_submitted_task_runs(project_id):

    parameters = {}
    # pump up the task counter by creating artificial task runs
    flow = prefect.Flow(
        name="Test Flow",
        schedule=prefect.schedules.IntervalSchedule(
            start_date=pendulum.datetime(2018, 1, 1),
            interval=datetime.timedelta(days=1),
        ),
    )
    for i in range(config.queued_runs_returned_limit):
        flow.add_task(prefect.Parameter(f"x{i}", default=1))
        parameters.update({f"x{i}": 1})

    flow_id = await api.flows.create_flow(
        project_id=project_id, serialized_flow=flow.serialize()
    )

    flow_run = await api.runs.create_flow_run(flow_id=flow_id, parameters=parameters)
    tasks = await models.Task.where({"flow_id": {"_eq": flow_id}}).get("id")

    for task in tasks:
        task_run = await api.runs.get_or_create_task_run(
            flow_run_id=flow_run, task_id=task.id, map_index=None
        )
        await api.states.set_task_run_state(task_run_id=task_run, state=Submitted())
