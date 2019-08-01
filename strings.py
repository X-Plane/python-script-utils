from typing import Iterable, Any


def quoted(stringlike):
    return '"%s"' % stringlike

def print_all(stringlikes: Iterable[Any], prefix='', suffix='\n'):
    for s in stringlikes:
        print('%s%s' % (prefix, s), end=suffix)
