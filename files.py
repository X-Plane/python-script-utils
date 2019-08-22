import hashlib
import os
import urllib.request
from pathlib import Path
from typing import Union, Iterable, List, Callable

Pathlike = Union[Path, str]
MaybePathlike = Union[Pathlike, None]

def dir_size(directory: Path) -> int: return file_sizes(f for f in directory.iterdir() if f.is_file())
def file_size_bytes(f: Pathlike) -> int: return os.path.getsize(str(f))
def file_sizes_bytes(files: Iterable[Pathlike]) -> int: return sum(file_size_bytes(f) for f in files)
file_size = file_size_bytes
file_sizes = file_sizes_bytes


def read_from_web_or_disk(url_or_path: Union[Path, str]):
    path = str(url_or_path)
    if path.startswith('http'):
        response = urllib.request.urlopen(path)
        return response.read().decode('utf-8')
    else:
        with open(path) as f:
            return f.read()

def subdirectories(dir: Pathlike) -> Iterable[Path]:
    assert Path(dir).is_dir(), 'Directory %s does not exist' % dir
    return (d for d in Path(dir).glob('*') if d.is_dir())

def files_recursive(dir: Pathlike) -> Iterable[Path]:
    assert Path(dir).is_dir(), 'Directory %s does not exist' % dir
    return (file_or_directory for file_or_directory in Path(dir).glob('**/*') if file_or_directory.is_file())

def files_recursive_filtered(dir: Pathlike, want_files_in_this_dir: Callable[[Path], bool]=lambda p: True) -> Iterable[Path]:
    assert Path(dir).is_dir(), 'Directory %s does not exist' % dir
    return (file_or_directory
            for file_or_directory in Path(dir).glob('**/*')
            if want_files_in_this_dir(file_or_directory.parent) and file_or_directory.is_file())

def resolve_symlinks(p: Pathlike) -> Path:
    """Unlke Path.resolve(), this does *not* throw an error if the path doesn't exist."""
    return Path(os.path.realpath(p))

def read_lines(p: Pathlike) -> List[str]:
    with Path(p).open() as f:
        return list(f.readlines())

def read_binary(p: Pathlike) -> bytes:
    return Path(p).open('rb').read()


def md5_hash(file_path_or_binary_data: Union[Path, bytes]) -> str:
    assert not isinstance(file_path_or_binary_data, str), 'str type is ambiguous: did you mean this as a file path or binary data?'
    if isinstance(file_path_or_binary_data, Path):
        return md5_hash(read_binary(file_path_or_binary_data))
    return hashlib.md5(file_path_or_binary_data).hexdigest()

