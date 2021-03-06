import collections
import itertools
import multiprocessing
import subprocess
from time import sleep
from typing import Any, Callable, Iterable, Set, Tuple, Union, List, Dict

take_first_n: Callable[[Iterable[Any], int], Any] = itertools.islice


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

    try:
        out = subprocess.run([str(arg) for arg in args],
                             stdout=None if 'capture_stdout' in kwargs and not kwargs['capture_stdout'] else subprocess.PIPE,
                             stderr=None if 'capture_stderr' in kwargs and not kwargs['capture_stderr'] else subprocess.PIPE,
                             cwd=str(kwargs['cwd']) if 'cwd' in kwargs else None,
                             check=kwargs['check'] if 'check' in kwargs else None)
    except subprocess.CalledProcessError as e:
        e.stderr = e.stderr.decode(errors='replace') if e.stderr else ''
        e.stdout = e.stdout.decode(errors='replace') if e.stdout else ''
        raise e
    else:  # Let's not make clients down the line deal with bytes objects
        out.stderr = out.stderr.decode(errors='replace') if out.stderr else ''
        out.stdout = out.stdout.decode(errors='replace') if out.stdout else ''
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

def flatten_dict_items(d: Dict[Any, Any]) -> List[Any]:
    """
    Recursively flattens a dict. Values in the dict must be either single values, lists of individual values,
    or other dicts which themselves have the same constraints.

    >>> flatten_dict_items(collections.OrderedDict(a=1, b=2, c=3))
    [1, 2, 3]
    >>> flatten_dict_items(collections.OrderedDict(a=[1, 2, 3], b=[4, 5, 6], c=[7, 8, 9]))
    [1, 2, 3, 4, 5, 6, 7, 8, 9]
    >>> flatten_dict_items(collections.OrderedDict(a=1, b=[2, 2.25, 2.5, 2.75], c=3))
    [1, 2, 2.25, 2.5, 2.75, 3]
    >>> flatten_dict_items(collections.OrderedDict(a=1, b=collections.OrderedDict(d=2, e=[2.25, 2.5, 2.75], f=2.8), c=[3, 4, 5]))
    [1, 2, 2.25, 2.5, 2.75, 2.8, 3, 4, 5]
    """
    out = []
    for key, item_or_items in d.items():
        if isinstance(item_or_items, collections.Mapping):  # dict-like
            out += flatten_dict_items(item_or_items)
        elif isinstance(item_or_items, collections.Iterable):
            out += list(item_or_items)
        else:  # must be an individual value
            out.append(item_or_items)
    return out

def partition(pred: Callable[[Any], bool], iterable: Iterable[Any]) -> Tuple[Iterable[Any], Iterable[Any]]:
    """Use a predicate to partition entries into false entries and true entries
    E.g, partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9"""
    t1, t2 = itertools.tee(iterable)
    return itertools.filterfalse(pred, t1), filter(pred, t2)

def reified_partition(pred: Callable[[Any], bool], iterable: Iterable[Any]) -> Tuple[List[Any], List[Any]]:
    """partition() with its return value as a pair of lists, not generators"""
    p1, p2 = partition(pred, iterable)
    return list(p1), list(p2)

def reified_filter(pred: Callable[[Any], bool], iterable: Iterable[Any]) -> List[Any]:
    return list(filter(pred, iterable))

def reified_chain(*args):
    return list(itertools.chain(*args))

def retry(action: Callable, max_tries=5):
    for attempted in range(max_tries):
        try:
            return action()
        except:
            sleep(attempted + 1)
    return action()
