from prefect_server.utilities.collections import chunked_iterable


def test_chunked_iterable_of_list():
    chunks = [chunk for chunk in chunked_iterable(list(range(10)), 4)]
    expected_chunks = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
    assert chunks == expected_chunks


def test_chunked_iterable_of_empty_iterable():
    chunks = [chunk for chunk in chunked_iterable([], 4)]
    assert len(chunks) == 0
