import asyncio
import random
from datetime import timedelta
from typing import Union

import pendulum

from prefect_server import config, utilities


class LoopService:
    """
    Loop services are relatively lightweight maintenance routines that need to run periodically.

    This class makes it straightforward to design and integrate them. Users only need to
    define the `run_once` coroutine to describe the behavior of the service on each loop.
    """

    # if set, and no `loop_seconds` is provided, the service will attempt to load
    # `loop_seconds` from this config key
    loop_seconds_config_key = None
    # if no loop_seconds_config_key is provided, this will be the default
    loop_seconds_default = 600

    def __init__(self, loop_seconds: Union[float, int] = None):
        if loop_seconds is None:
            if self.loop_seconds_config_key:

                # split the key on '.' and recurse
                split_keys = self.loop_seconds_config_key.split(".")
                cfg = config
                for key in split_keys[:-1]:
                    cfg = cfg.get(key, {})
                loop_seconds = cfg.get(split_keys[-1])
            else:
                loop_seconds = self.loop_seconds_default
        if loop_seconds == 0:
            raise ValueError("`loop_seconds` must be greater than 0.")

        self.loop_seconds = float(loop_seconds)
        self.name = type(self).__name__
        self.logger = utilities.logging.get_logger(self.name)

    async def run(self) -> None:
        """
        Run the service forever.

        The service will start after a delay randomly chosen between 1 and `loop_seconds`.
        This helps ensure that multiple services are staggered uniformly.
        """

        # randomly stagger the start time
        startup_delay = random.randint(0, int(self.loop_seconds))
        self.logger.info(
            f"{self.name} will start after an initial sleep of {startup_delay} seconds..."
        )
        await asyncio.sleep(startup_delay)

        last_log = pendulum.now("UTC")

        while True:
            start_time = pendulum.now("UTC")

            try:
                await self.run_once()

            # if an error is raised, log and continue
            except Exception as exc:
                self.logger.error(f"Unexpected error: {repr(exc)}")

            # next run is every "loop seconds" after each previous run *started*
            next_run = start_time.add(seconds=self.loop_seconds)

            # don't log more than once every 5 minutes
            if pendulum.now("UTC") - last_log > timedelta(minutes=5):
                self.logger.debug(
                    f"Heartbeat from {self.name}: next run at {next_run.replace(microsecond=0)}"
                )
                last_log = pendulum.now("UTC")

            await asyncio.sleep((next_run - pendulum.now("UTC")).total_seconds())

    async def run_once(self) -> None:
        """
        Run the service once.

        Users should override this method.
        """
        raise NotImplementedError()
