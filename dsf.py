import math
import re
import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from typing import FrozenSet, Tuple, Union, List, Iterable

from utils.data_processing import checked_subprocess
from utils.files import Pathlike, read_binary, sanitize_file_name, write_file, file_sizes


class LatLon(tuple):
    def __new__(cls, lat: int, lon: int):
        self = super(LatLon, cls).__new__(cls, (lat, lon))
        return self

    def __str__(self): return '%+03d%+04d' % (self[0], self[1])

    @property
    def folder_and_file_stem(self) -> str:
        return '%+03d%+04d/%s' % (self[0] - self[0] % 10, self[1] - self[1] % 10, self)

    @property
    def lon(self): return self[1]

    @property
    def lat(self): return self[0]

    @staticmethod
    def from_str(dsf_file_or_folder: Pathlike) -> 'LatLon':
        assert is_dsf_like_path(dsf_file_or_folder), 'Expected format +00+000.ext, but got ' + dsf_file_or_folder
        last_component = Path(dsf_file_or_folder).name
        return LatLon(lat=int(last_component[:3]), lon=int(last_component[3:7]))

    @staticmethod
    def from_airport(apt: 'Airport') -> 'LatLon':
        return LatLon(lat=math.floor(apt.latitude), lon=math.floor(apt.longitude))


dsf_re = re.compile(r'^([+-]\d{2})([+-]\d{3})$')
def is_dsf_like_path(file_or_dir: Pathlike, check_parent_dir: bool=False) -> True:
    """
    @param check_parent_dir: True if we should require the file to also be contained in a DSF-numbered (10x10) directory

    >>> is_dsf_like_path('foo/bar/+18-050.png', check_parent_dir=False)
    True
    >>> is_dsf_like_path('foo/bar/+18-050.png', check_parent_dir=True)  # Parent dir doesn't match DSF folder naming conventions
    False
    >>> is_dsf_like_path('foo/bar/18-050.png')  # Missing leading +/- on 18
    False
    >>> is_dsf_like_path('P-A18-150.acf')
    False
    >>> is_dsf_like_path('-18+150.foo')  # File extension doesn't matter
    True
    >>> is_dsf_like_path('+00+000')
    True
    >>> is_dsf_like_path('+00+000', check_parent_dir=True)  # No parent dir
    False
    >>> is_dsf_like_path('00+000/+09+004', check_parent_dir=True)  # Missing leading +/-
    False
    >>> is_dsf_like_path('+00+000/+09+004', check_parent_dir=True)
    True
    """
    def component_is_dsf_like(path_component: str):
        return bool(dsf_re.match(path_component))

    p = Path(file_or_dir)
    return component_is_dsf_like(p.stem) and \
           (not check_parent_dir or component_is_dsf_like(p.parent.name))

def dsf_folder(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+40-130'"""
    return path_to_tile.parent.name

def dsf_file(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+47-123'"""
    return path_to_tile.stem

def dsf_folder_and_file(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+40-130/+47-123'"""
    return "%s/%s" % (path_to_tile.parent.name, path_to_tile.stem)

def all_tiles(degree_width_height: int=1, min_lat=-60, max_lat=74) -> FrozenSet[LatLon]:
    return frozenset(LatLon(lat=lat, lon=lon)
                     for lon in range(-180, 179, degree_width_height)
                     for lat in range(min_lat, max_lat, degree_width_height))

def tiles_on_disk(dsf_structured_directory: Path, file_suffix: str='.dsf') -> FrozenSet[LatLon]:
    assert dsf_structured_directory.is_dir(), f'No such directory {dsf_structured_directory}'
    return frozenset(LatLon.from_str(f.stem)
                     for f in dsf_structured_directory.glob('*/*')
                     if is_dsf_like_path(f) and f.suffix == file_suffix and f.is_file())

def dsf_tile_bbox(file_name: Union[LatLon, Path], width_height_deg=1) -> Tuple[int, int, int, int]:
    base_lat_lon = file_name if isinstance(file_name, LatLon) else LatLon.from_str(file_name.stem)
    return base_lat_lon.lon,                    base_lat_lon.lat, \
           base_lat_lon.lon + width_height_deg, base_lat_lon.lat + width_height_deg


def all_10x10s() -> FrozenSet[LatLon]:
    return all_tiles(10)

def tiles_in_10x10(folder_lat_lon: Union[str, Path, LatLon]) -> FrozenSet[LatLon]:
    if isinstance(folder_lat_lon, Path):
        folder_lat_lon = LatLon.from_str(folder_lat_lon.name)
    elif isinstance(folder_lat_lon, str):
        folder_lat_lon = LatLon.from_str(folder_lat_lon)

    return frozenset(LatLon(lat=lat, lon=lon)
                     for lon in range(folder_lat_lon.lon, folder_lat_lon.lon + 10)
                     for lat in range(folder_lat_lon.lat, folder_lat_lon.lat + 10))


def dsf_is_7zipped(dsf_path: Path) -> bool:
    with dsf_path.open('rb') as dsf:
        return dsf.read(2) == b'7z'

def unzip_dsf(zipped_dsf_path: Path, unzipped_out_path: Path):
    out_dir = sanitize_file_name(zipped_dsf_path.name)
    # Irritatingly, 7za doesn't let us just specify the final output path for a single file... only the name of the directory we'll unzip "everything" into
    checked_subprocess('7za', 'e', zipped_dsf_path, f'-o{out_dir}')
    unzipped_dsf = Path(out_dir) / zipped_dsf_path.name
    unzipped_dsf.replace(unzipped_out_path)  # Move the newly unzipped file to the target path
    shutil.rmtree(out_dir)  # Clean up temp unzip directory
    return unzipped_out_path

def zip_dsf(unzipped_dsf: Path, zipped_out_path: Path):
    tmp_7z_file = zipped_out_path.with_suffix('.7z')
    checked_subprocess('7za', 'a', '-m0=LZMA', tmp_7z_file, unzipped_dsf)
    zipped_out_path.unlink()
    tmp_7z_file.rename(zipped_out_path)


def dsf_to_txt(source_dsf_path: Path, dsf_tool: Path) -> str:
    """
    Converts the (binary) DSF to text form (in memory, rather than on disk, for easy manipulation).
    Leaves no temp files around on disk.
    """
    assert source_dsf_path.suffix == '.dsf'
    if not source_dsf_path.is_file():
        raise FileNotFoundError('Could not find source DSF %s' % source_dsf_path)

    is_zipped = dsf_is_7zipped(source_dsf_path)
    if is_zipped:
        dsf_to_read = source_dsf_path.with_suffix('.unzipped')
        unzip_dsf(source_dsf_path, dsf_to_read)
    else:
        dsf_to_read = source_dsf_path

    result = checked_subprocess(dsf_tool, '-dsf2text', dsf_to_read, '-')
    if 'ERROR:' in result.stderr:
        raise RuntimeError(f'Error converting DSF:\n{result.stderr}')
    end_of_output = '# Result code: '

    if is_zipped:
        dsf_to_read.unlink()
    return result.stdout.split(end_of_output)[0]


def txt_to_dsf(dsf_txt_lines: Union[str, Iterable[str]], target_dsf_path: Path, dsf_tool: Path, compress: bool=True) -> subprocess.CompletedProcess:
    """Writes your DSF text lines to a binary DSF file"""
    assert target_dsf_path.suffix == '.dsf'

    tmp_txt_path: Path = target_dsf_path.with_suffix('.txt')
    write_file(dsf_txt_lines, tmp_txt_path)

    target_dsf_path.parent.mkdir(parents=True, exist_ok=True)
    result = checked_subprocess(dsf_tool, '-text2dsf', tmp_txt_path, target_dsf_path)
    tmp_txt_path.unlink()

    if compress:
        zip_dsf(target_dsf_path, target_dsf_path)
    return result


with suppress(ModuleNotFoundError):
    import shapefile  # from pyshp

    class Shapefile(shapefile.Reader):
        """Syntactic sugar around a shapefile reader"""
        def __init__(self, shp_path: Pathlike, skip_dbf=True):
            self.skip_dbf = skip_dbf
            shp_path = Path(shp_path)
            assert shp_path.suffix == '.shp', '%s is not a shapefile (.shp)' % shp_path
            assert shp_path.is_file(), '%s does not exist on disk' % shp_path
            super(Shapefile, self).__init__(str(shp_path))
            if skip_dbf:
                self.dbf = None
                self.numRecords = 0
            assert self.shp, 'Failed to load shapefile %s' % shp_path

        def load_dbf(self, shp_name):
            if not self.skip_dbf:
                super().load_dbf(shp_name)

        def iterRecords(self): return [] if self.skip_dbf else super().iterRecords()

        @staticmethod
        def rename_set(shp_path: Path, new_stem: str) -> Path:
            def target_with_suffix(suffix): return (shp_path.parent / new_stem).with_suffix(suffix)

            assert shp_path.stem != new_stem
            for source in Shapefile.all_extensions(shp_path):
                try:
                    shutil.move(source, target_with_suffix(source.suffix))
                except FileNotFoundError as e:
                    if not source.suffix == '.dbf':  # Suppress errors if the non-essential DBF file is missing
                        raise e
            return target_with_suffix('.shp')

        @staticmethod
        def delete_set(shp_path: Path):
            for f in Shapefile.all_extensions(shp_path):
                try:
                    f.unlink()
                except FileNotFoundError as e:
                    if not f.suffix == '.dbf':  # Suppress errors if the non-essential DBF file is missing
                        raise e

        @staticmethod
        def all_extensions(shp_path: Path) -> List[Path]:
            return [(shp_path.parent / shp_path.name).with_suffix(ext) for ext in ['.shp', '.shx', '.dbf']]

        @staticmethod
        def set_size(shp_path: Pathlike) -> int:
            """:return size in bytes of the sum of .shp, .shx, and .dbf file"""
            return file_sizes(Shapefile.all_extensions(shp_path))

