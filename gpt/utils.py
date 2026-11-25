import itertools
from typing import Iterable, List, Iterator, TypeVar

T = TypeVar('T')

def chunked(iterable: Iterable[T], size: int) -> Iterator[List[T]]:
    """Yield successive chunks of size `size` from `iterable`."""
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk

