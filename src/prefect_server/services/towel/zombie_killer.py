import asyncio

import pendulum

from prefect.engine.state import Failed, Retrying
from prefect.utilities.graphql import EnumValue, with_args
from prefect import api
from prefect_server.database import models, orm
from prefect_server.services.loop_service import LoopService


class ZombieKiller(LoopService):
    loop_seconds_default = 120

    async def run_once(self) -> int:
        """
        Zombie tasks are tasks that claim to be Running, but haven't updated their heartbeat.

        This method marks them as failed.

        Returns:
            - int: the number of task runs that were killed
        """
        time = pendulum.now("utc").subtract(minutes=2)

        zombies = 0
        i = 0
        limit = 1000

        while True:

            task_runs = await models.TaskRun.where(
                {
                    # the task run is RUNNING
                    "state": {"_eq": "Running"},
                    # ... but the heartbeat is stale
                    "heartbeat": {"_lte": str(time)},
                    # ... and the flow has heartbeats enabled
                    "task": {
                        "flow": {
                            "flow_group": {
                                "_not": {
                                    "settings": {
                                        "_contains": {"heartbeat_enabled": False}
                                    }
                                }
                            }
                        }
                    },
                }
            ).get(
                selection_set={
                    "id": True,
                    "flow_run_id": True,
                    # get information about retries from task
                    "task": {"max_retries", "retry_delay"},
                    # count the number of retrying states for this task run
                    with_args(
                        "retry_count: states_aggregate",
                        {"where": {"state": {"_eq": "Retrying"}}},
                    ): {"aggregate": {"count"}},
                },
                limit=limit,
                offset=i * limit,
                order_by={"updated": EnumValue("desc")},
                apply_schema=False,
            )
            i += 1

            if not task_runs:
                break

            self.logger.info(f"Zombie killer found {len(task_runs)} task runs.")

            # Set task run states to failed
            for tr in task_runs:
                try:
                    # if retries are available, mark as retrying
                    if tr.retry_count.aggregate.count < (tr.task.max_retries or 0):
                        message = (
                            "No heartbeat detected from the remote task; retrying the run."
                            f"This will be retry {tr.retry_count.aggregate.count + 1} of {tr.task.max_retries}."
                        )
                        retry_delay = orm._as_timedelta(tr.task.retry_delay or "0")
                        await api.states.set_task_run_state(
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
                        await api.states.set_task_run_state(
                            task_run_id=tr.id, state=Failed(message=message),
                        )

                    # log the state change to the task run
                    await api.logs.create_logs(
                        [
                            dict(
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


if __name__ == "__main__":
    asyncio.run(ZombieKiller().run())
