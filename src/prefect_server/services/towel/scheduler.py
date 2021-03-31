import asyncio

from prefect import api, models
from prefect.utilities.graphql import EnumValue

from prefect_server.services.loop_service import LoopService


class Scheduler(LoopService):
    """
    The Scheduler is a service that creates new flow runs for flows with active schedules.

    Flows that are eligible for scheduling have the following properties:
        - the schedule is active
        - the flow is not archived
    """
    loop_seconds_default = 150

    async def run_once(self) -> int:
        """
        Returns:
            - int: The number of scheduled runs
        """

        runs_scheduled = 0
        iterations = 0

        # visit all flows in batches of 500
        while True:

            flows = await models.Flow.where(
                {
                    # schedule is active
                    "is_schedule_active": {"_eq": True},
                    # flow is not archived
                    "archived": {"_eq": False},
                }
            ).get(
                selection_set={
                    "id",
                },
                # deterministic sort for batching
                order_by=[{"id": EnumValue("desc")}],
                limit=500,
                offset=500 * iterations,
            )

            if not flows:
                break

            iterations += 1

            # concurrently schedule all runs
            all_run_ids = await asyncio.gather(
                *[api.flows.schedule_flow_runs(flow.id) for flow in flows],
                return_exceptions=True,
            )
            runs_scheduled += sum(
                len(ids)
                for ids in all_run_ids
                # only include lists to avoid errors
                if isinstance(ids, list)
            )

        self.logger.info(f"Scheduled {runs_scheduled} flow runs.")
        return runs_scheduled
