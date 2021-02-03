import asyncio
import pytest

from prefect_server.services.loop_service import LoopService

COUNTER = 0


class LoopServiceTest(LoopService):
    loop_seconds_default = 0.1

    async def run_once(self):
        global COUNTER
        COUNTER += 1
        print(COUNTER)


@pytest.fixture(autouse=True)
def reset():
    global COUNTER
    COUNTER = 0
    # reset running flag
    LoopServiceTest.is_running = True


async def test_stop_a_running_loop_service():
    ls = LoopServiceTest()
    assert ls.is_running is True

    # start running service in background
    task = asyncio.create_task(ls.run())
    await asyncio.sleep(0.3)

    # stop the service
    ls.stop()
    await task

    # the counter was incremented 3 times
    assert COUNTER == 3
    assert ls.is_running is False

    # sleep and ensure the service isn't running anymore
    await asyncio.sleep(0.1)
    assert COUNTER == 3


async def test_overriding_loop_seconds_default():
    ls = LoopServiceTest(loop_seconds=1)

    # start running service in background
    task = asyncio.create_task(ls.run())
    await asyncio.sleep(0.3)
    ls.stop()
    await task

    # the counter was incremented 1 time
    assert COUNTER == 1


async def test_loop_service_with_run_time_longer_than_loop_interval(caplog):
    class LongLoopService(LoopService):
        loop_seconds_default = 0.1

        async def run_once(self):
            # sleep for longer than the loop seconds
            await asyncio.sleep(0.2)
            global COUNTER
            COUNTER += 1

    ls = LongLoopService()
    task = asyncio.create_task(ls.run())
    # the task takes at least 0.2 seconds to run
    # so it should ignore its loop interval and run
    # at least twice in 0.4 seconds
    await asyncio.sleep(0.4)
    ls.stop()
    await task

    assert COUNTER > 1

    msg = "LongLoopService took longer to run than its loop interval of 0.1 seconds."
    assert any(msg in record.message for record in caplog.records)
