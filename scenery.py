#!/usr/bin/env python3
import functools
from contextlib import suppress
from functools import reduce
from pathlib import Path
from typing import Dict, Iterable, Optional

from utils.data_processing import synchronous_map
from utils.files import Pathlike, read_lines, correct_case
from utils.strings import compress_spaces

LibraryTxt = Dict[str, Path]  # maps library.txt virtual paths to paths on disk


def fix_path_case_and_slashes_in_library_txt_line(line: str, from_library_txt: Path, assert_no_missing_assets: bool=False) -> str:
    slashes_corrected = line.replace('\\', '/')
    single_spaces = compress_spaces(slashes_corrected).strip()
    with suppress(ValueError):
        kw, lib_path, suspect_disk_path = single_spaces.split(' ', 2)
        if kw in ('EXPORT', 'EXPORT_EXTEND'):
            line_before_path = slashes_corrected.rsplit(str(suspect_disk_path), maxsplit=1)[0]
            rel_path = case_correct_asset_path(from_library_txt.parent / Path(suspect_disk_path),
                                               from_library_txt, assert_no_missing_assets)
            return f"{line_before_path}{rel_path}\n"
    return line


def fix_path_case_and_slashes_in_library_txt(library_txt: Path):
    out_lines = synchronous_map(functools.partial(fix_path_case_and_slashes_in_library_txt_line, from_library_txt=library_txt),
                                read_lines(library_txt))
    with library_txt.open('w') as out_file:
        out_file.writelines(out_lines)


def case_correct_asset_path(absolute_asset_path: Path, referenced_from_file: Optional[Path], assert_exists: bool=False) -> Path:
    def get_case_corrected_absolute_asset_path(absolute_asset_path: Path, assert_exists: bool=False) -> Path:
        if absolute_asset_path.is_file():
            return correct_case(absolute_asset_path)
        else:
            obe_version = absolute_asset_path.with_suffix('.obe')
            was_converted_to_obe = absolute_asset_path.suffix == '.obj' and obe_version.is_file()
            assert not assert_exists or was_converted_to_obe, f'Missing asset {absolute_asset_path}'
            if was_converted_to_obe:
                return correct_case(obe_version).with_suffix('.obj')
            else:
                return absolute_asset_path

    abs_path = get_case_corrected_absolute_asset_path(absolute_asset_path, assert_exists)
    if referenced_from_file:
        return abs_path.relative_to(referenced_from_file.parent)
    else:
        return abs_path


def read_library_txt(library_txt_path: Pathlike, validate_paths: bool=False) -> LibraryTxt:
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


def read_all_library_txts(library_txts: Iterable[Pathlike], validate_paths: bool=False) -> LibraryTxt:
    """Reads all library.txt files and combines them into one mega LibraryTxt"""
    return reduce(lambda accum_dict, lib_txt_path: {**accum_dict, **read_library_txt(lib_txt_path, validate_paths)},
                  library_txts,
                  {})

def read_scenery_pack_library_txts(scenery_pack: Pathlike, validate_paths: bool=False) -> LibraryTxt:
    """Recursively reads all library.txt files in the scenery pack and combines them into one mega LibraryTxt"""
    return read_all_library_txts(Path(scenery_pack).glob('**/library.txt'), validate_paths)

