import itertools
from typing import Iterable


def chunked_iterable(iterable: Iterable, size: int):
    """
    Yield chunks of a certain size from an iterable

    Args:
        - iterable (Iterable): An iterable
        - size (int): The size of chunks to return

    Yields:
        tuple: A chunk of the iterable
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk
