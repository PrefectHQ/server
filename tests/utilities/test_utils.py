from prefect_server.utilities.utils import get_chunk


def test_get_chunk_of_list():
    chunks = [chunk for chunk in get_chunk(list(range(10)), 4)]
    expected_chunks = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
    assert chunks == expected_chunks


def test_get_chunk_of_empty_iterable():
    chunks = [chunk for chunk in get_chunk([], 4)]
    assert len(chunks) == 0
