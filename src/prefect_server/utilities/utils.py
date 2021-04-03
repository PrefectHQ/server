from typing import Iterable


def get_chunk(iterable: Iterable, chunk_size: int):
    """
    Yield chunks of a certain size from an iterable

    Args:
        - iterable (Iterable): An iterable
        - chunk_size (int): The size of chunks to return

    Yields:
        tuple: A chunk of the iterable
    """
    result = []
    for item in iterable:
        result.append(item)
        if len(result) == chunk_size:
            yield tuple(result)
            result = []
    if len(result) > 0:
        yield tuple(result)
