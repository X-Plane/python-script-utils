import shutil
from contextlib import suppress
from pathlib import Path
from typing import FrozenSet, Tuple, Union, List, Iterable

class LatLon(tuple):
    def __new__(cls, lat: int, lon: int):
        self = super(LatLon, cls).__new__(cls, (lat, lon))
        return self

    def __str__(self): return '%+03d%+04d' % (self[0], self[1])

    @property
    def folder_and_file_stem(self) -> str:
        return '%+03d%+04d/%s' % (self[0] - self[0] % 10, self[1] - self[1] % 10, self)

    @staticmethod
    def from_str(dsf_file_or_folder: str):
        assert is_dsf_like_path(dsf_file_or_folder), 'Expected format +00+000, but got ' + dsf_file_or_folder
        return LatLon(lat=int(dsf_file_or_folder[:3]), lon=int(dsf_file_or_folder[3:]))


def is_dsf_like_path(file_or_dir: Pathlike):
    stem = file_or_dir.stem if isinstance(file_or_dir, Path) else Path(file_or_dir).stem
    return len(stem) == 7 and stem[0] in ('+', '-') and stem[3] in ('+', '-')

def dsf_folder(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+40-130'"""
    return path_to_tile.parent.name

def dsf_file(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+47-123'"""
    return path_to_tile.stem

def dsf_folder_and_file(path_to_tile: Path) -> str:
    """Transforms 'foo/bar/+40-130/+47-123.pvr' into '+40-130/+47-123'"""
    return "%s/%s" % (path_to_tile.parent.name, path_to_tile.stem)

def all_tiles(degree_width_height: int=1) -> FrozenSet[LatLon]:
    return frozenset(LatLon(lat=lat, lon=lon)
                     for lon in range(-180, 171, degree_width_height)
                     for lat in range(-80, 71, degree_width_height))

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

