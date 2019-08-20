import os
import urllib.request
from pathlib import Path
from typing import Union, Iterable, List, Callable

Pathlike = Union[Path, str]
MaybePathlike = Union[Pathlike, None]

def dir_size(directory: Path) -> int: return file_sizes(f for f in directory.iterdir() if f.is_file())
def file_size(f: Path) -> int: return os.path.getsize(str(f))
def file_sizes(files: Iterable[Path]) -> int: return sum(file_size(f) for f in files)


def read_from_web_or_disk(url_or_path: Union[Path, str]):
    path = str(url_or_path)
    if path.startswith('http'):
        response = urllib.request.urlopen(path)
        return response.read().decode('utf-8')
    else:
        with open(path) as f:
            return f.read()

def subdirectories(dir: Pathlike) -> Iterable[Path]:
    assert dir.is_dir(), 'Directory %s does not exist' % dir
    return (d for d in Path(dir).glob('*') if d.is_dir())

def files_recursive(dir: Pathlike) -> Iterable[Path]:
    assert dir.is_dir(), 'Directory %s does not exist' % dir
    return (file_or_directory for file_or_directory in Path(dir).glob('**/*') if file_or_directory.is_file())

def files_recursive_filtered(dir: Pathlike, want_files_in_this_dir: Callable[[Path], bool]=lambda p: True) -> Iterable[Path]:
    assert dir.is_dir(), 'Directory %s does not exist' % dir
    return (file_or_directory
            for file_or_directory in Path(dir).glob('**/*')
            if want_files_in_this_dir(file_or_directory.parent) and file_or_directory.is_file())

def resolve_symlinks(p: Pathlike) -> Path:
    """Unlke Path.resolve(), this does *not* throw an error if the path doesn't exist."""
    return Path(os.path.realpath(p))

def read_lines(p: Pathlike) -> List[str]:
    with Path(p).open() as f:
        return list(f.readlines())
