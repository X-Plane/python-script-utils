import multiprocessing
from typing import Iterable, Callable, Any


def pipeline(functions: Iterable[Callable], initial_data: Any, parallel: bool=True) -> Any:
    """
    Modeled after Node.js async.series().
    Takes a series of transformations to map over your data.
    Passes the result of mapping the first function into the second,
    the result of which gets passed into the third, etc.
    """
    data = initial_data
    if parallel:
        with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
            for f in functions:
                data = pool.map(f, data)
    else:
        nongenerating_map = lambda fn, dta: list(map(fn, dta))
        for f in functions:
            data = nongenerating_map(f, data)
    return data


