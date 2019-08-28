import itertools
import multiprocessing
import subprocess
from contextlib import suppress
from time import sleep
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
        for f in functions:
            data = synchronous_map(f, data)
    return data


def parallel_map(function: Callable, data: Iterable[Any]) -> Iterable[Any]:
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        return pool.map(function, data)


def synchronous_map(fn: Callable, data: Iterable[Any]):
    return list(map(fn, data))


def synchronous_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    if len(args) == 1:
        if isinstance(args[0], list):
            args = args[0]
        elif isinstance(args[0], str):
            args = args[0].split(' ')

    out = subprocess.run([str(arg) for arg in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         cwd=str(kwargs['cwd']) if 'cwd' in kwargs else None,
                         check=kwargs['check'] if 'check' in kwargs else None)
    # Let's not make clients down the line deal with bytes objeces
    with suppress(UnicodeDecodeError):
        out.stderr = out.stderr.decode() if out.stderr else ''
    with suppress(UnicodeDecodeError):
        out.stdout = out.stdout.decode() if out.stdout else ''
    return out


def checked_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    kwargs['check'] = True
    return synchronous_subprocess(*args, **kwargs)


def remove_none(collection: Iterable[Any]) -> List[Any]:
    return [item for item in collection if item is not None]


def flatten(list_of_list_of_lists: Union[List[Any], Tuple[Any], Set[Any]]) -> Iterable[Any]:
    for i in list_of_list_of_lists:
        if isinstance(i, (list, tuple, set)):
            for j in flatten(i):
                yield j
        else:
            yield i


def partition(pred: Callable[[Any], bool], iterable: Iterable[Any]) -> Tuple[Iterable[Any], Iterable[Any]]:
    """Use a predicate to partition entries into false entries and true entries
    E.g, partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9"""
    t1, t2 = itertools.tee(iterable)
    return itertools.filterfalse(pred, t1), filter(pred, t2)

def reified_partition(pred: Callable[[Any], bool], iterable: Iterable[Any]) -> Tuple[List[Any], List[Any]]:
    """partition() with its return value as a pair of lists, not generators"""
    p1, p2 = partition(pred, iterable)
    return list(p1), list(p2)


def retry(action: Callable, max_tries=5):
    attempted = 0
    while True:
        try:
            return action()
        except Exception as e:
            attempted += 1
            if attempted == max_tries:
                raise e
            sleep(attempted)
