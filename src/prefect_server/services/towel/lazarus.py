import asyncio

import pendulum

import prefect
from prefect.engine.state import Failed, Paused, Running, Scheduled
from prefect.utilities.graphql import EnumValue
from prefect_server import api, config
from prefect_server.database import models
from prefect_server.services.loop_service import LoopService

# lazarus should not restart flows with states that are scheduled, running, or
# indicative of future runs (like Paused)
SCHEDULED_STATES = [
    s
    for s in prefect.engine.state.__dict__.values()
    if isinstance(s, type) and issubclass(s, (Scheduled, Running))
]
LAZARUS_EXCLUDE = [s.__name__ for s in SCHEDULED_STATES + [Paused]]


class Lazarus(LoopService):

    loop_seconds_default = 600

    async def run_once(self) -> int:
        """
        The Lazarus process revives any flow runs that are submitted or running but have no tasks in
        a running or scheduled state. The heartbeat must be stale in order to avoid race conditions
        with transitioning tasks.

        Returns:
            - int: the number of flow runs that were scheduled
        """
        time = pendulum.now("utc").subtract(minutes=10)

        flow_runs = await models.FlowRun.where(
            {
                # get runs that are currently running or submitted
                "state": {"_in": ["Running", "Submitted"]},
                # that were last updated some time ago
                "heartbeat": {"_lte": str(time)},
                # but have no task runs in a near-running state
                "_not": {"task_runs": {"state": {"_in": LAZARUS_EXCLUDE}}},
                # and whose do not have heartbeats or lazarus enabled
                "_not": {
                    "flow": {
                        "flow_group": {
                            "_or": [
                                {
                                    "settings": {
                                        "_contains": {"heartbeat_enabled": False}
                                    }
                                },
                                {"settings": {"_contains": {"lazarus_enabled": False}}},
                            ]
                        }
                    }
                },
            }
        ).get(
            selection_set={"id", "version", "times_resurrected"},
            order_by={"heartbeat": EnumValue("asc")},
        )
        self.logger.info(
            f"Found {len(flow_runs)} flow runs to reschedule with a Lazarus process"
        )

        if not flow_runs:
            return 0

        run_count = 0

        for fr in flow_runs:
            # check how many times it's been resurrected, otherwise it will repeat ad infinitum
            if (
                fr.times_resurrected
                < config.services.lazarus.resurrection_attempt_limit
            ):
                try:
                    # Set flow run state to scheduled
                    await api.states.set_flow_run_state(
                        flow_run_id=fr.id,
                        state=Scheduled(message="Rescheduled by a Lazarus process."),
                    )

                    # increment the times_resurrected value for the flow run
                    await models.FlowRun.where(id=fr.id).update(
                        set=dict(times_resurrected=fr.times_resurrected + 1)
                    )
                    # log flow run state change
                    await api.logs.create_logs(
                        [
                            dict(
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
                await api.states.set_flow_run_state(
                    flow_run_id=fr.id, state=Failed(message=message),
                )
                # log flow run state change
                await api.logs.create_logs(
                    [
                        dict(
                            flow_run_id=fr.id,
                            name=f"{self.logger.name}.FlowRun",
                            message=message,
                            level="ERROR",
                        )
                    ]
                )

        self.logger.info(f"Lazarus process rescheduled {run_count} flow runs.")
        return run_count


if __name__ == "__main__":
    asyncio.run(Lazarus().run())
