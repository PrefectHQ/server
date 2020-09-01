import asyncio

from prefect_server.services.towel.lazarus import Lazarus
from prefect_server.services.towel.scheduler import Scheduler
from prefect_server.services.towel.zombie_killer import ZombieKiller


async def run_towel():
    await asyncio.gather(
        Lazarus().run(),
        Scheduler().run(),
        ZombieKiller().run(),
    )


if __name__ == "__main__":
    asyncio.run(run_towel())
