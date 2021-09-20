import time

from prefect_server.utilities.collections import chunked_iterable, TimedUniqueValueStore


def test_chunked_iterable_of_list():
    chunks = [chunk for chunk in chunked_iterable(list(range(10)), 4)]
    expected_chunks = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
    assert chunks == expected_chunks


def test_chunked_iterable_of_empty_iterable():
    chunks = [chunk for chunk in chunked_iterable([], 4)]
    assert len(chunks) == 0


class TestTimedUniqueValueStore:

    def test_add_and_expire(self):
        store = TimedUniqueValueStore()
        added = store.add_and_expire("value1", duration=2)
        assert added
        assert store.exists("value1")
        time.sleep(3)
        assert not store.exists("value1")

    def test_add_and_expire_unique(self):
        store = TimedUniqueValueStore()
        added = store.add_and_expire("value1", duration=2)
        assert added
        assert store.exists("value1")
        added = store.add_and_expire("value1", duration=3)
        assert not added
