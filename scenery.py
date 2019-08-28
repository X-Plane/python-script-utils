#!/env/bin python3
from contextlib import suppress
from functools import reduce
from pathlib import Path
from typing import Dict, Iterable
from utils.files import Pathlike, read_lines
from utils.strings import compress_spaces

LibraryTxt = Dict[str, Path]  # maps library.txt virtual paths to paths on disk

def read_library_txt(library_txt_path: Pathlike) -> LibraryTxt:
    out = {}
    assert Path(library_txt_path).name == 'library.txt'
    for line in read_lines(library_txt_path):
        single_spaces = compress_spaces(line)
        with suppress(ValueError):  # Just skip any malformed lines
            slashes_corrected = single_spaces.replace('\\', '/')
            kw, lib_path, real_path = slashes_corrected.split(' ', 2)
            real_path = Path(real_path)
            if kw in ('EXPORT', 'EXPORT_EXTEND'):
                out[lib_path] = Path(real_path)
    return out


def read_all_library_txts(library_txts: Iterable[Pathlike]) -> LibraryTxt:
    """Reads all library.txt files and combines them into one mega LibraryTxt"""
    return reduce(lambda accum_dict, lib_txt_path: {**accum_dict, **read_library_txt(lib_txt_path)},
                  library_txts,
                  {})

def read_scenery_pack_library_txts(scenery_pack: Pathlike) -> LibraryTxt:
    """Recursively reads all library.txt files in the scenery pack and combines them into one mega LibraryTxt"""
    return read_all_library_txts(Path(scenery_pack).glob('**/library.txt'))

