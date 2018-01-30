from helpers.cache import cache_decorator
from helpers.cache import Cache


def test_cache(tmpdir):

    cache = Cache(tmpdir)
    cached = cache_decorator(cache)

    num_calls = 0

    @cached
    def get_num_calls():
        """This function returns number of times it was called,
        so we can determine if the result was restored from cache
        or was it recalculated.
        """
        nonlocal num_calls
        num_calls += 1
        return num_calls

    # first time it should be one
    assert get_num_calls() == 1

    # and second time, again: one (as long as cache system works)
    assert get_num_calls() == 1

    # test caching with args
    last_result = 1

    def accumulative_mul(a):
        """Mul a*b, where b is the result of the previous multiplication,
        or one if there was no previous multiplication.
        """
        nonlocal last_result
        last_result *= a
        return last_result

    assert accumulative_mul(5) == 5
    assert accumulative_mul(5) == 5 * 5

    last_result = 1

    cached_accumulative_mul = cached(accumulative_mul)

    assert cached_accumulative_mul(5) == 5
    assert cached_accumulative_mul(5) == 5

    last_result = 10    # this should change nothing
    assert cached_accumulative_mul(5) == 5

    # unless the cache is deleted
    cached_accumulative_mul.clean(5)

    assert cached_accumulative_mul(5) == 50
    assert cached_accumulative_mul(5) == 50

    # handle keywords:

    base = 5

    @cached
    def calc(a=2):
        return base**a

    assert calc() == 25
    assert calc(a=1) == 5

    base = 1
    assert calc() == 25
    assert calc(a=1) == 5
    assert calc(a=2) == 1
