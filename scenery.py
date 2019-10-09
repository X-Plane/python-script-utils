#!/usr/bin/env python3
import functools
from contextlib import suppress
from functools import reduce
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from utils.data_processing import synchronous_map
from utils.files import Pathlike, read_lines, correct_case
from utils.strings import compress_spaces

LibraryTxt = Dict[str, Path]  # maps library.txt virtual paths to paths on disk


def normalize_dir_char(scenery_asset: Pathlike):
    if isinstance(scenery_asset, str):
        return scenery_asset.replace('\\', '/')
    else:
        return Path(normalize_dir_char(str(scenery_asset)))


def fix_path_case_and_slashes_in_library_txt_line(line: str, from_library_txt: Path, assert_no_missing_assets: bool=False) -> str:
    slashes_corrected = normalize_dir_char(line)
    single_spaces = compress_spaces(slashes_corrected).strip()
    with suppress(ValueError):
        kw, lib_path, suspect_disk_path = single_spaces.split(' ', 2)
        if kw in ('EXPORT', 'EXPORT_EXTEND'):
            line_before_path = slashes_corrected.rsplit(str(suspect_disk_path), maxsplit=1)[0]
            rel_path, exists = case_correct_asset_path(from_library_txt.parent / Path(suspect_disk_path),
                                                       from_library_txt, assert_no_missing_assets)
            return f"{line_before_path}{rel_path}\n"
    return line


def fix_path_case_in_asset_line_if_exists(asset_line: str, asset_tokens: Iterable[str], referenced_in_file: Path) -> Optional[str]:
    with suppress(ValueError):
        tokens = compress_spaces(asset_line).strip().split(' ')
        if len(tokens) > 1 and tokens[0] in asset_tokens:
            suspect_disk_path = tokens[-1]
            if suspect_disk_path.startswith('lib/'):  # This is a library path... we won't try to look it up
                return asset_line
            else:
                line_before_path = asset_line.rsplit(str(suspect_disk_path), maxsplit=1)[0]
                correct_rel_path, exists = case_correct_asset_path(referenced_in_file.parent / Path(normalize_dir_char(suspect_disk_path)),
                                                                   referenced_in_file)
                if exists:
                    return f"{normalize_dir_char(line_before_path)}{correct_rel_path}\n"
                else:
                    return None  # File doesn't exist; prune it!
    return asset_line


def fix_path_case_and_slashes_in_library_txt(library_txt: Path):
    out_lines = synchronous_map(functools.partial(fix_path_case_and_slashes_in_library_txt_line, from_library_txt=library_txt),
                                read_lines(library_txt))
    with library_txt.open('w') as out_file:
        out_file.writelines(out_lines)


def case_correct_asset_path(absolute_asset_path: Path, referenced_from_file: Optional[Path], assert_exists: bool=False) -> Tuple[Path, bool]:
    """@return The case corrected path, as much as we could case-correct, plus a bool indicating whether the file exists on disk"""
    def get_case_corrected_absolute_asset_path(absolute_asset_path: Path, assert_exists: bool=False) -> Tuple[Path, bool]:
        def variant_suffixes_to_try(p: Path) -> Iterable[str]:
            for overload_set in (['.obj', '.obe'], ['.dds', '.png', '.pvr', '.etc', '.PNG', '.DDS']):
                if p.suffix in overload_set:
                    return filter(lambda suffix: suffix != p.suffix, overload_set)
            return []

        input_path_exists = absolute_asset_path.is_file()
        if not input_path_exists:
            for variant_suffix in variant_suffixes_to_try(absolute_asset_path):
                alternate_version = absolute_asset_path.with_suffix(variant_suffix)
                assert not assert_exists or alternate_version.is_file(), f'Missing asset {absolute_asset_path}'
                if alternate_version.is_file():
                    suffix_to_use = absolute_asset_path.suffix if absolute_asset_path.suffix.lower() != alternate_version.suffix.lower() else absolute_asset_path.suffix
                    return correct_case(alternate_version).with_suffix(suffix_to_use), True
        return correct_case(absolute_asset_path), input_path_exists

    abs_path, exists_on_disk = get_case_corrected_absolute_asset_path(absolute_asset_path, assert_exists)
    if referenced_from_file:
        return abs_path.relative_to(referenced_from_file.parent), exists_on_disk
    else:
        return abs_path, exists_on_disk


def read_library_txt(library_txt_path: Pathlike, validate_paths: bool=False) -> LibraryTxt:
    out = {}
    assert Path(library_txt_path).name == 'library.txt'
    for line in read_lines(library_txt_path):
        single_spaces = compress_spaces(line)
        with suppress(ValueError):  # Just skip any malformed lines
            slashes_corrected = normalize_dir_char(single_spaces)
            kw, lib_path, real_path_str = slashes_corrected.split(' ', 2)
            real_path = Path(real_path_str)
            if kw in ('EXPORT', 'EXPORT_EXTEND'):
                out[lib_path] = real_path
                assert not validate_paths or (library_txt_path.parent / real_path).is_file(), f'Path {real_path} from {library_txt_path} does not exist on disk'
                assert not validate_paths or str(real_path) == real_path_str, f'Path {real_path} from {library_txt_path} has a case mismatch---this will cause problems on case-sensitive filesystems'
    return out


def read_all_library_txts(library_txts: Iterable[Pathlike], validate_paths: bool=False) -> LibraryTxt:
    """Reads all library.txt files and combines them into one mega LibraryTxt"""
    return reduce(lambda accum_dict, lib_txt_path: {**accum_dict, **read_library_txt(lib_txt_path, validate_paths)},
                  library_txts,
                  {})

def read_scenery_pack_library_txts(scenery_pack: Pathlike, validate_paths: bool=False) -> LibraryTxt:
    """Recursively reads all library.txt files in the scenery pack and combines them into one mega LibraryTxt"""
    return read_all_library_txts(Path(scenery_pack).glob('**/library.txt'), validate_paths)

