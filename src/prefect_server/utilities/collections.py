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


class TimedUniqueValueStore:
    """
    Stores unique values for a specific amount of time.

    Args:
        - duration (float, int): the number of seconds to store a value before removing it
    """

    def __init__(self, duration: Union[float, int] = 10):
        self.values = set()
        self.lock = threading.Lock()
        self.duration = duration

    def add_and_expire(self, value: Hashable, duration: Optional[float, int] = None) -> bool:
        """
        Add a unique value to store and kick off a timer to remove it

        Args:
            - value (Hashable): value to store, must be hashable and
                able to be stored in a set
            - duration (float, int, optional): the number of seconds to store a value
                before removing it. Defaults to self.duration if not provided
        Returns:
            - bool: `True` if the value did not already exist in the store
                and is successfully added, otherwise `False`
        """
        if duration is None:
            duration = self.duration

        with self.lock:
            if value in self.values:
                return False
            else:
                self.values.add(value)
                threading.Timer(duration, self.remove, kwargs={"value": value}).start()
                return True

    def remove(self, value: Hashable):
        """
        Remove a value from the store

        Args:
            - value (Hashable): value to remove from store
        """
        with self.lock:
            self.values.discard(value)

    def exists(self, value: Hashable):
        """
        Check if a value exists in the store

        Args:
            - value (Hashable): value to remove from store
        """
        with self.lock:
            return value in self.values
