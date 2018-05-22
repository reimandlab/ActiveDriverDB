from pathlib import Path
from typing import Callable

from diskcache import Cache as DiskCache


class Cache(DiskCache):

    def __init__(self, directory, *args, cache_root=None, **kwargs):
        if not cache_root:
            cache_root = Path(__file__).absolute().parent.parent
        path = Path(directory)
        if not path.is_absolute():
            path = cache_root / path
        super().__init__(str(path), *args, **kwargs)


def cache_decorator(cache: Cache) -> Callable:
    """Create a decorator caching results of the function calls.

    The cache is specific to the function name and provided arguments.

    The determination of arguments equality relies on dictionary-like
    interface of diskcache.Cache, which may differ from those
    defined in __hash__ or __eq__ methods.
    """

    def create_key(name, *args, **kwargs):
        args = [arg.name if hasattr(arg, 'name') else arg for arg in args]
        if kwargs:
            return (name, *args, kwargs)
        return (name, *args)

    def cached(func: Callable):

        name = func.__name__

        def clean_cache(*args, **kwargs):
            key = create_key(name, *args, **kwargs)
            del cache[key]

        def cache_manager(*args, **kwargs):

            key = create_key(name, *args, **kwargs)

            if key not in cache:
                cache[key] = func(*args, **kwargs)
            else:
                print(f'Using cached result of {name}({", ".join(map(repr, args))})')

            return cache[key]

        cache_manager.__name__ = f'cache_manager_of_{name}'
        cache_manager.name = name
        cache_manager.clean = clean_cache

        return cache_manager

    return cached
