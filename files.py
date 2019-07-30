import os
from pathlib import Path
from typing import Union, Iterable

Pathlike = Union[Path, str]
MaybePathlike = Union[Pathlike, None]

def dir_size(directory: Path) -> int: return file_sizes(f for f in directory.iterdir() if f.is_file())
def file_size(f: Path) -> int: return os.path.getsize(str(f))
def file_sizes(files: Iterable[Path]) -> int: return sum(file_size(f) for f in files)

