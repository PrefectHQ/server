import itertools
from typing import Hashable, Iterable, Optional, Union
import threading


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


class ExpiringSet:
    """
    Stores values in a set for a specific amount of time.

    Args:
        - duration_seconds (float, int): the number of seconds to put a value in the set before removing it
    """

    def __init__(self, duration_seconds: Union[float, int] = 10):
        self.values = set()
        self.lock = threading.Lock()
        self.duration_seconds = duration_seconds

    def add(
        self, value: Hashable, duration_seconds: Optional[Union[float, int]] = None
    ) -> bool:
        """
        Add a value to set and kick off a timer to remove it

        Args:
            - value (Hashable): value to add, must be hashable and
                able to be stored in a set
            - duration_seconds (float, int, optional): the number of seconds to add a value for
                before removing it. Defaults to self.duration if not provided
        Returns:
            - bool: `True` if the value did not already exist in the set
                and is successfully added, otherwise `False`
        """
        if duration_seconds is None:
            duration_seconds = self.duration_seconds

        with self.lock:
            if value in self.values:
                return False
            else:
                self.values.add(value)
                threading.Timer(
                    duration_seconds, self.remove, kwargs={"value": value}
                ).start()
                return True

    def remove(self, value: Hashable):
        """
        Remove a value from the set

        Args:
            - value (Hashable): value to remove from set
        """
        with self.lock:
            self.values.discard(value)

    def exists(self, value: Hashable):
        """
        Check if a value exists in the set

        Args:
            - value (Hashable): value to remove from set
        """
        with self.lock:
            return value in self.values
