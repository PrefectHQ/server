import asyncio

import click
import pendulum

import prefect
from prefect import api, models
from prefect.engine.state import Submitted
from prefect.utilities.graphql import EnumValue, with_args
from prefect_server.utilities import logging

state_schema = prefect.serialization.state.StateSchema()
environment_schema = prefect.serialization.environment.EnvironmentSchema()
storage_schema = prefect.serialization.storage.StorageSchema()


class LocalAgent:
    """
    The LocalAgent is used for testing the system locally. It queries the database for
    executions and runs them in the local process.
    """

    def __init__(self, loop_interval=None):
        self.loop_interval = loop_interval or 0.25
        self.logger = logging.get_logger(__name__)

    async def run_scheduled(self, flow_id=None):
        """
        Queries for any flow runs that are SCHEDULED, OR any flow runs that have SCHEDULED
        task runs [if the flow run itself is RUNNING]. Sets all Scheduled runs to Submitted
        and runs the flow.

        If a flow_id is provided, only flow runs of that flow are matched.
        """
        now = pendulum.now()
        flow_runs = await models.FlowRun.where(
            {
                "_or": [
                    {"state_start_time": {"_lte": str(now)}},
                    {
                        "state": {"_eq": "Running"},
                        "task_runs": {"state_start_time": {"_lte": str(now)}},
                    },
                ],
                "flow_id": {"_eq": flow_id},
            }
        ).get(
            selection_set={
                "id": True,
                "version": True,
                "tenant_id": True,
                "state": True,
                "serialized_state": True,
                "parameters": True,
                "flow": {"id", "environment", "name", "storage"},
                with_args(
                    "task_runs", {"where": {"state_start_time": {"_lte": str(now)}}}
                ): {"id", "version", "task_id", "serialized_state"},
            },
            limit=100,
            order_by={"state_start_time": EnumValue("asc")},
        )
        for fr in flow_runs:

            skip_counter = 0

            fr_serialized_state = state_schema.load(fr.serialized_state)

            # set the flow run state to submitted, if it's scheduled
            if fr_serialized_state.is_scheduled():
                try:
                    await api.states.set_flow_run_state(
                        flow_run_id=fr.id,
                        state=Submitted(
                            message="Submitted for execution",
                            state=fr_serialized_state,
                        ),
                    )
                except ValueError as exc:
                    skip_counter += 1
                    if "Update failed" not in str(exc):
                        raise

            # set each task run state to submitted, if it's scheduled
            for tr in fr.task_runs:
                tr_serialized_state = state_schema.load(tr.serialized_state)

                try:
                    await api.states.set_task_run_state(
                        task_run_id=tr.id,
                        state=Submitted(
                            message="Submitted for execution",
                            state=tr_serialized_state,
                        ),
                    )
                except ValueError as exc:
                    skip_counter += 1
                    if "Update failed" not in str(exc):
                        raise

            # none of the states were set, so we shouldn't bother running
            if skip_counter == 1 + len(fr.task_runs):
                continue

            self.logger.info(f'Submitting flow run "{fr.id}" for execution.')

            # run the flow
            self.run_flow(
                flow_name=fr.flow.name,
                storage=storage_schema.load(fr.flow.storage),
                environment=environment_schema.load(fr.flow.environment),
                config={
                    "cloud.api": f"http://localhost:4200",
                    "cloud.graphql": "http://localhost:4200",
                    "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
                    "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
                    "engine.executor.default_class": "prefect.engine.executors.LocalExecutor",
                },
                context={"flow_run_id": fr.id},
            )

    def run_flow(self, flow_name, storage, environment, config, context):
        with prefect.utilities.configuration.set_temporary_config(config):
            with prefect.context(context):
                environment.execute(storage.get_flow(storage.flows[flow_name]))

    async def start(self):
        self.logger.info(f"Starting {type(self).__name__}...")
        while True:
            try:
                await self.run_scheduled()
            except Exception as exc:
                self.logger.error(exc)
            await asyncio.sleep(self.loop_interval)


@click.command()
def start() -> None:
    asyncio.run(LocalAgent().start())
