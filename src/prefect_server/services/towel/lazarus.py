import asyncio
import datetime
from typing import Any, Dict

import pendulum

import prefect
from prefect import models
from prefect.engine.state import Failed, Running, Scheduled
from prefect.utilities.graphql import EnumValue
from prefect_server import config
from prefect_server.services.loop_service import LoopService

# lazarus should not restart flows with states that are scheduled, running, or
# indicative of future runs (like Paused)
LAZARUS_EXCLUDE = [
    s.__name__
    for s in prefect.engine.state.__dict__.values()
    if isinstance(s, type) and issubclass(s, (Scheduled, Running))
]


class Lazarus(LoopService):

    loop_seconds_default = 600

    async def run_once(self) -> None:
        """
        The Lazarus process revives any flow runs that are submitted or running but have no tasks in
        a running or scheduled state. The heartbeat must be stale in order to avoid race conditions
        with transitioning tasks.

        Returns:
            - int: the number of flow runs that were scheduled
        """

        return await self.reschedule_flow_runs()

    async def get_flow_runs_where_clause(
        self, heartbeat_cutoff: datetime.datetime
    ) -> Dict[str, Any]:
        """
        Returns a `where` clause for loading flow runs from the DB
        """
        return {
            # get runs that are currently running or submitted
            "state": {"_in": ["Running", "Submitted"]},
            # that were last updated some time ago
            "heartbeat": {"_lte": str(heartbeat_cutoff)},
            "_and": [
                # but have no task runs in a near-running state
                {"_not": {"task_runs": {"state": {"_in": LAZARUS_EXCLUDE}}}},
                # and whose do not have heartbeats or lazarus enabled
                {
                    "_not": {
                        "flow": {
                            "flow_group": {
                                "_or": [
                                    {
                                        "settings": {
                                            "_contains": {"heartbeat_enabled": False}
                                        }
                                    },
                                    {
                                        "settings": {
                                            "_contains": {"lazarus_enabled": False}
                                        }
                                    },
                                ]
                            }
                        }
                    }
                },
            ],
        }

    async def reschedule_flow_runs(
        self, heartbeat_cutoff: datetime.datetime = None
    ) -> int:
        heartbeat_cutoff = heartbeat_cutoff or pendulum.now("utc").subtract(minutes=10)
        run_count = 0

        where_clause = await self.get_flow_runs_where_clause(
            heartbeat_cutoff=heartbeat_cutoff
        )
        flow_runs = await models.FlowRun.where(where_clause).get(
            selection_set={"id", "version", "tenant_id", "times_resurrected"},
            order_by={"updated": EnumValue("asc")},
            limit=5000,
        )

        if flow_runs:
            self.logger.info(
                f"Found {len(flow_runs)} flow runs to reschedule with a Lazarus process"
            )

        for fr in flow_runs:
            # check how many times it's been resurrected, otherwise it will repeat ad infinitum
            if (
                fr.times_resurrected
                < config.services.lazarus.resurrection_attempt_limit
            ):
                try:
                    # Set flow run state to scheduled
                    await prefect.api.states.set_flow_run_state(
                        flow_run_id=fr.id,
                        state=Scheduled(message="Rescheduled by a Lazarus process."),
                    )

                    # increment the times_resurrected value for the flow run
                    await models.FlowRun.where(id=fr.id).update(
                        set=dict(times_resurrected=fr.times_resurrected + 1)
                    )
                    # log flow run state change
                    await prefect.api.logs.create_logs(
                        [
                            dict(
                                tenant_id=fr.tenant_id,
                                flow_run_id=fr.id,
                                name=f"{self.logger.name}.FlowRun",
                                message=(
                                    "Rescheduled by a Lazarus process. "
                                    f"This is attempt {fr.times_resurrected + 1}."
                                ),
                                level="INFO",
                            )
                        ]
                    )

                    run_count += 1

                except ValueError as exc:
                    # if the error contains "Update failed", it was a version-lock situation
                    # and we don't need to interrupt execution on its account. If it was
                    # anything else, raise an error.
                    if "Update failed" in str(exc):
                        self.logger.error(exc)
                    else:
                        raise
            else:

                message = (
                    "A Lazarus process attempted to reschedule this run "
                    f"{config.services.lazarus.resurrection_attempt_limit} times "
                    "without success. Marking as failed."
                )
                # Set flow run state to failed
                await prefect.api.states.set_flow_run_state(
                    flow_run_id=fr.id,
                    state=Failed(message=message),
                )
                # log flow run state change
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

        if run_count:
            self.logger.info(f"Lazarus process rescheduled {run_count} flow runs.")
        return run_count


if __name__ == "__main__":
    asyncio.run(Lazarus().run())
