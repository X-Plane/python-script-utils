import multiprocessing
import subprocess
from typing import Any, Callable, Iterable, Set, Tuple, Union, List


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


def synchronous_subprocess(*args: Any) -> subprocess.CompletedProcess:
    if len(args) == 1 and isinstance(args[0], list):
        args = args[0]

    out = subprocess.run([str(arg) for arg in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Let's not make clients down the line deal with bytes objeces
    out.stderr = out.stderr.decode() if out.stderr else ''
    out.stdout = out.stdout.decode() if out.stdout else ''
    return out


def remove_none(collection: Iterable[Any]) -> List[Any]:
    return [item for item in collection if item is not None]


def flatten(list_of_list_of_lists: Union[List[Any], Tuple[Any], Set[Any]]) -> Iterable[Any]:
    for i in list_of_list_of_lists:
        if isinstance(i, (list, tuple, set)):
            for j in flatten(i):
                yield j
        else:
            yield i

