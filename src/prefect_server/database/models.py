import datetime
from typing import Any, Dict, List, Optional

import pendulum
import pydantic

import prefect
from prefect.utilities import plugins
from prefect_server.database.orm import HasuraModel, UUIDString

models = plugins.MODELS


@plugins.register_model("Tenant")
class Tenant(HasuraModel):
    __hasura_type__ = "tenant"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    name: Optional[str] = None
    slug: Optional[str] = None
    info: Dict[str, Any] = None
    settings: Dict[str, Any] = None

    projects: List["Project"] = None


@plugins.register_model("Project")
class Project(HasuraModel):
    __hasura_type__ = "project"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    name: Optional[str] = None
    description: Optional[str] = None

    # relationships
    tenant: Tenant = None
    flows: List["Flow"] = None


@plugins.register_model("Flow")
class Flow(HasuraModel):
    __hasura_type__ = "flow"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    project_id: UUIDString = None
    archived: bool = None
    schedule: Dict[str, Any] = None
    is_schedule_active: bool = None
    version: int = None
    version_group_id: Optional[str] = None
    core_version: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    serialized_flow: Dict[str, Any] = None
    environment: Dict[str, Any] = None
    run_config: Dict[str, Any] = None
    storage: Dict[str, Any] = None
    parameters: List[Dict[str, Any]] = None
    flow_group_id: UUIDString = None

    # relationships
    project: Project = None
    tenant: Tenant = None
    tasks: List["Task"] = None
    edges: List["Edge"] = None
    flow_runs: List["FlowRun"] = None
    versions: List["Flow"] = None
    flow_group: "FlowGroup" = None


@plugins.register_model("Task")
class Task(HasuraModel):
    __hasura_type__ = "task"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_id: UUIDString = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    max_retries: int = None
    retry_delay: datetime.timedelta = None
    trigger: Optional[str] = None
    tags: List[str] = None
    mapped: bool = None
    auto_generated: bool = None
    cache_key: Optional[str] = None
    is_root_task: bool = None
    is_terminal_task: bool = None
    is_reference_task: bool = None


@plugins.register_model("Edge")
class Edge(HasuraModel):
    __hasura_type__ = "edge"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_id: UUIDString = None
    upstream_task_id: UUIDString = None
    downstream_task_id: UUIDString = None
    key: Optional[str] = None
    mapped: bool = None


@plugins.register_model("FlowRun")
class FlowRun(HasuraModel):
    __hasura_type__ = "flow_run"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_id: UUIDString = None
    parameters: Dict[str, Any] = None
    labels: List[str] = None
    run_config: Dict[str, Any] = None
    context: Dict[str, Any] = None
    version: int = None
    heartbeat: datetime.datetime = None
    scheduled_start_time: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    auto_scheduled: bool = None
    name: Optional[str] = None
    times_resurrected: int = None
    idempotency_key: Optional[str] = None
    agent_id: UUIDString = None

    # state fields
    state: Optional[str] = None
    state_timestamp: datetime.datetime = None
    state_message: Optional[str] = None
    state_result: Any = None
    state_start_time: datetime.datetime = None
    serialized_state: Dict[str, Any] = None

    # relationships
    tenant: Tenant = None
    flow: Flow = None
    states: List["FlowRunState"] = None
    task_runs: List["TaskRun"] = None
    logs: List["Log"] = None


@plugins.register_model("TaskRun")
class TaskRun(HasuraModel):
    __hasura_type__ = "task_run"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_run_id: UUIDString = None
    task_id: UUIDString = None
    map_index: int = None
    version: int = None
    heartbeat: datetime.datetime = None
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None
    cache_key: Optional[str] = None
    name: Optional[str] = None

    # state fields
    state: Optional[str] = None
    state_timestamp: datetime.datetime = None
    state_message: Optional[str] = None
    state_result: Any = None
    state_start_time: datetime.datetime = None
    serialized_state: Dict[str, Any] = None

    # relationships
    flow_run: FlowRun = None
    task: Task = None
    states: List["TaskRunState"] = None
    logs: List["Log"] = None


@plugins.register_model("FlowRunState")
class FlowRunState(HasuraModel):
    __hasura_type__ = "flow_run_state"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    message: Optional[str] = None
    result: Optional[str] = None
    start_time: datetime.datetime = None
    state: Optional[str] = None
    version: int = None
    serialized_state: Dict[str, Any] = None

    # relationships
    flow_run: FlowRun = None

    @staticmethod
    def fields_from_state(state: prefect.engine.state.State, timestamp=None):
        """
        Returns a dict that contains fields that could be inferred from a state object
        """
        if timestamp is None:
            timestamp = pendulum.now("utc")

        # update all state columns
        return dict(
            state=type(state).__name__,
            timestamp=timestamp,
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )


@plugins.register_model("TaskRunState")
class TaskRunState(HasuraModel):
    __hasura_type__ = "task_run_state"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    task_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    message: Optional[str] = None
    result: Optional[str] = None
    start_time: datetime.datetime = None
    state: Optional[str] = None
    version: int = None
    serialized_state: Dict[str, Any] = None

    # relationships
    task_run: TaskRun = None

    @staticmethod
    def fields_from_state(state: prefect.engine.state.State, timestamp=None):
        """
        Returns a dict that contains fields that could be inferred from a state object
        """
        if timestamp is None:
            timestamp = pendulum.now("utc")

        # update all state columns
        return dict(
            state=type(state).__name__,
            timestamp=timestamp,
            message=state.message,
            result=state.result,
            start_time=getattr(state, "start_time", None),
            serialized_state=state.serialize(),
        )


@plugins.register_model("Log")
class Log(HasuraModel):
    __hasura_type__ = "log"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    flow_run_id: UUIDString = None
    task_run_id: UUIDString = None
    timestamp: datetime.datetime = None
    name: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    info: Dict[str, Any] = None


@plugins.register_model("CloudHook")
class CloudHook(HasuraModel):
    __hasura_type__ = "cloud_hook"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    version_group_id: Optional[str] = None
    states: List[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    config: Optional[dict] = None
    active: bool = None


@plugins.register_model("FlowGroup")
class FlowGroup(HasuraModel):
    __hasura_type__ = "flow_group"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    description: Optional[str] = None
    tenant_id: UUIDString = None
    name: Optional[str] = None
    settings: Optional[dict] = None
    default_parameters: Optional[dict] = None
    schedule: Optional[dict] = None
    labels: List[str] = None
    run_config: Dict[str, Any] = None

    # relationships
    flows: List["Flow"] = None


@plugins.register_model("Message")
class Message(HasuraModel):
    __hasura_type__ = "message"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    user_id: UUIDString = None
    read: bool = None
    type: Optional[str] = None
    text: Optional[str] = None
    content: Optional[dict] = None


@plugins.register_model("AgentConfig")
class AgentConfig(HasuraModel):
    __hasura_type__ = "agent_config"

    id: UUIDString = None
    created: datetime.datetime = None
    updated: datetime.datetime = None
    tenant_id: UUIDString = None
    name: Optional[str] = None
    settings: Optional[dict] = None


@plugins.register_model("Agent")
class Agent(HasuraModel):
    __hasura_type__ = "agent"

    id: UUIDString = None
    created: datetime.datetime = None
    tenant_id: UUIDString = None
    agent_config_id: UUIDString = None
    name: Optional[str] = None
    type: Optional[str] = None
    core_version: Optional[str] = None
    labels: List[str] = None
    last_queried: datetime.datetime = None


@plugins.register_model("TaskRunArtifact")
class TaskRunArtifact(HasuraModel):
    __hasura_type__ = "task_run_artifact"

    id: UUIDString = None
    created: datetime.datetime = None
    tenant_id: UUIDString = None
    task_run_id: UUIDString = None
    kind: Optional[str] = None
    data: Optional[dict] = None


# process forward references for all Pydantic models (meaning string class names)
for obj in list(locals().values()):
    if isinstance(obj, type) and issubclass(obj, pydantic.BaseModel):
        obj.update_forward_refs()
