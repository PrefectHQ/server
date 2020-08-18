import asyncio
import pytest

from prefect_server.services.loop_service import LoopService

COUNTER = 0


class LoopServiceTest(LoopService):
    loop_seconds_default = 0.1

    async def run_once(self):
        global COUNTER
        COUNTER += 1


@pytest.fixture(autouse=True)
def reset_counter():
    global COUNTER
    COUNTER = 0


async def test_stop_a_running_loop_service():
    ls = LoopServiceTest()
    assert ls._stop_running is False

    # start running service in background
    asyncio.create_task(ls.run())
    await asyncio.sleep(0.3)

    # stop the service
    ls.stop()

    # the counter was incremented 3 times
    assert COUNTER == 3
    assert ls._stop_running is True

    # sleep and ensure the service isn't running anymore
    await asyncio.sleep(0.1)
    assert COUNTER == 3


async def test_overriding_loop_seconds_default():
    ls = LoopServiceTest(loop_seconds=0.2)

    # start running service in background
    asyncio.create_task(ls.run())
    await asyncio.sleep(0.2)

    ls.stop()

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
    asyncio.create_task(ls.run())
    # if the task loops immediately, it should run twice in
    # just over .4 seconds
    await asyncio.sleep(0.41)
    ls.stop()

    assert COUNTER == 2

    msg = "LongLoopService took longer to run than its loop interval of 0.1 seconds."
    assert any(msg in record.message for record in caplog.records)
