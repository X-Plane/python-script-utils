import re
from typing import Iterable, Any


def quoted(stringlike):
    return '"%s"' % stringlike

def compress_spaces(line: str) -> str:
    """Compresses all instances of multiple whitespace in a row down to a single space"""
    return re.sub(r'\s+', ' ', line).strip() + '\n'

def print_all(stringlikes: Iterable[Any], prefix='', suffix='\n'):
    for s in stringlikes:
        print('%s%s' % (prefix, s), end=suffix)
