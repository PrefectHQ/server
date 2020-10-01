import asyncio
import datetime
from typing import Any, Dict

import pendulum

import prefect
from prefect import models
from prefect.engine.state import Failed, Retrying
from prefect.utilities.graphql import EnumValue, with_args
from prefect_server.database import orm
from prefect_server.services.loop_service import LoopService


class ZombieKiller(LoopService):
    loop_seconds_default = 120

    async def get_flow_runs_where_clause(
        self, heartbeat_cutoff: datetime.datetime
    ) -> Dict[str, Any]:
        """
        Returns a `where` clause for loading zombie flow runs from the DB
        """
        return {
            # the flow run is CANCELLING
            "state": {"_eq": "Cancelling"},
            # ... but the heartbeat is stale
            "heartbeat": {"_lte": str(heartbeat_cutoff)},
            # ... and the flow has heartbeats enabled
            "flow": {
                "flow_group": {
                    "_not": {"settings": {"_contains": {"heartbeat_enabled": False}}}
                }
            },
        }

    async def reap_zombie_cancelling_flow_runs(
        self, heartbeat_cutoff: datetime.datetime = None
    ) -> int:
        """
        Marks flow runs that are in a `Cancelling` state but fail to move to a
        `Cancelled` state as `Failed`.

        Returns:
            - int: the number of flow runs that were handled
        """
        zombies = 0
        heartbeat_cutoff = heartbeat_cutoff or pendulum.now("utc").subtract(minutes=10)

        where_clause = await self.get_flow_runs_where_clause(
            heartbeat_cutoff=heartbeat_cutoff
        )
        flow_runs = await models.FlowRun.where(where_clause).get(
            selection_set={"id", "tenant_id"},
            limit=5000,
            order_by={"updated": EnumValue("desc")},
        )

        if flow_runs:
            self.logger.info(f"Zombie killer found {len(flow_runs)} flow runs.")

        # Set flow run states to failed
        for fr in flow_runs:
            try:
                message = "No heartbeat detected from the flow run; marking the run as failed."
                await prefect.api.states.set_flow_run_state(
                    flow_run_id=fr.id,
                    state=Failed(message=message),
                )

                # log the state change to the flow run
                await prefect.api.logs.create_logs(
                    [
                        dict(
                            tenant_id=fr.tenant_id,
                            flow_run_id=fr.id,
                            name=f"{self.logger.name}.FlowRun",
                            message=message,
                            level="ERROR",
                        )
                    ]
                )

                zombies += 1

            except ValueError:
                self.logger.error("Error updating flow run %s", fr.id, exc_info=True)

        if zombies:
            self.logger.info(f"Addressed {zombies} zombie flow runs.")

        return zombies

    async def get_task_runs_where_clause(
        self, heartbeat_cutoff: datetime.datetime
    ) -> Dict[str, Any]:
        """
        Returns a `where` clause for loading zombie task runs from the DB
        """
        return {
            # the task run is RUNNING
            "state": {"_eq": "Running"},
            # ... but the heartbeat is stale
            "heartbeat": {"_lte": str(heartbeat_cutoff)},
            # ... and the flow has heartbeats enabled
            "task": {
                "flow": {
                    "flow_group": {
                        "_not": {
                            "settings": {"_contains": {"heartbeat_enabled": False}}
                        }
                    }
                }
            },
        }

    async def reap_zombie_task_runs(
        self, heartbeat_cutoff: datetime.datetime = None
    ) -> int:
        """
        Zombie tasks are tasks that claim to be Running, but haven't updated their heartbeat.

        This method either retries them or marks them as failed.

        Returns:
            - int: the number of zombie task runs that were handled
        """
        zombies = 0
        heartbeat_cutoff = heartbeat_cutoff or pendulum.now("utc").subtract(minutes=10)

        where_clause = await self.get_task_runs_where_clause(
            heartbeat_cutoff=heartbeat_cutoff
        )

        task_runs = await models.TaskRun.where(where_clause).get(
            selection_set={
                "id": True,
                "flow_run_id": True,
                "tenant_id": True,
                # Information about the current flow run state
                "flow_run": {"state"},
                # get information about retries from task
                "task": {"max_retries", "retry_delay"},
                # count the number of retrying states for this task run
                with_args(
                    "retry_count: states_aggregate",
                    {"where": {"state": {"_eq": "Retrying"}}},
                ): {"aggregate": {"count"}},
            },
            limit=5000,
            order_by={"updated": EnumValue("desc")},
            apply_schema=False,
        )

        if task_runs:
            self.logger.info(f"Zombie killer found {len(task_runs)} task runs.")

        # Set task run states to failed
        for tr in task_runs:
            try:
                # if the flow run is running and retries are available, mark as retrying
                if (
                    tr.flow_run.state == "Running"
                    and tr.retry_count.aggregate.count < (tr.task.max_retries or 0)
                ):
                    message = (
                        "No heartbeat detected from the remote task; retrying the run."
                        f"This will be retry {tr.retry_count.aggregate.count + 1} of {tr.task.max_retries}."
                    )
                    retry_delay = orm._as_timedelta(tr.task.retry_delay or "0")
                    await prefect.api.states.set_task_run_state(
                        task_run_id=tr.id,
                        state=Retrying(
                            message=message,
                            run_count=tr.retry_count.aggregate.count + 1,
                            start_time=pendulum.now("UTC") + retry_delay,
                        ),
                    )

                # mark failed
                else:
                    message = "No heartbeat detected from the remote task; marking the run as failed."
                    await prefect.api.states.set_task_run_state(
                        task_run_id=tr.id,
                        state=Failed(message=message),
                    )

                # log the state change to the task run
                await prefect.api.logs.create_logs(
                    [
                        dict(
                            tenant_id=tr.tenant_id,
                            flow_run_id=tr.flow_run_id,
                            task_run_id=tr.id,
                            name=f"{self.logger.name}.TaskRun",
                            message=message,
                            level="ERROR",
                        )
                    ]
                )

                zombies += 1

            except ValueError as exc:
                self.logger.error(exc)

        if zombies:
            self.logger.info(f"Addressed {zombies} zombie task runs.")

        return zombies

    async def run_once(self) -> None:
        # reap task runs
        await self.reap_zombie_task_runs()

        # reap flow runs
        await self.reap_zombie_cancelling_flow_runs()


if __name__ == "__main__":
    asyncio.run(ZombieKiller().run())
