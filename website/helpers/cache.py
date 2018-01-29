from typing import Callable

from diskcache import Cache


def cache_decorator(cache: Cache) -> Callable:
    """Create a decorator caching results of the function calls.

    The cache is specific to the function name and provided arguments.

    The determination of arguments equality relies on dictionary-like
    interface of diskcache.Cache, which may differ from those
    defined in __hash__ or __eq__ methods.
    """

    def cached(func: Callable):

        name = func.__name__

        def clean_cache(*args):
            key = (name, *args)
            del cache[key]

        def cache_manager(*args):

            key = (name, *args)

            if key not in cache:
                cache[key] = func(*args)
            else:
                print(f'Using cached result of {name}({", ".join(map(repr, args))})')

            return cache[key]

        cache_manager.__name__ = f'cache_manager_of_{name}'
        cache_manager.clean = clean_cache

        return cache_manager

    return cached
