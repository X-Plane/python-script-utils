import logging
from collections import defaultdict, namedtuple
from dataclasses import dataclass
from urllib.error import URLError
from pathlib import Path
from typing import List, Iterable, Dict, Optional, Tuple, DefaultDict
from utils.files import read_from_web_or_disk, Pathlike
from utils.highwinds_cdn import CdnServer


@dataclass
class ComponentBlock:
    component_name: str
    cdn_subdomain: CdnServer
    package_path: str
    manifest_versions: List[int]
    require_auth: bool
    sim_version_low: int
    sim_version_high: int

    def __str__(self):
        return f'COMPONENT com.laminarresearch.xplane_10.{self.component_name}\n' \
               f'{self.cdn_subdomain.for_component_list()}\n' \
               f'{self.package_path}\n' \
               f'MANIFEST_VERSIONS {self.manifest_versions[0]} {self.manifest_versions[1]}\n' \
               f'REQUIRE_AUTH {int(self.require_auth)}\n' \
               f'SIM_VERSIONS {self.sim_version_low}-{self.sim_version_high}\n\n'

    @staticmethod
    def from_str(file_text: str):
        lines = file_text.strip().splitlines(keepends=False)
        assert len(lines) == 6, 'Expected exactly: SERVER, CDN subdomain, package path, MANIFEST_VERSION, REQUIRE_AUTH, SIM_VERSIONS lines'
        sim_versions_str = lines[5].split('SIM_VERSIONS ', maxsplit=1)[1].split()
        package_path = lines[2]
        assert package_path.startswith('/'), 'Your package path is not absolute on the server---this will go poorly for you!'
        return ComponentBlock(component_name=lines[0].split('com.laminarresearch.xplane_10.', maxsplit=1)[1],
                              cdn_subdomain=CdnServer.from_component_list_id(lines[1]),
                              package_path=package_path,
                              manifest_versions=[int(v) for v in lines[3].split('MANIFEST_VERSIONS ', maxsplit=1)[1].strip().split()],
                              require_auth=bool(lines[4].split('REQUIRE_AUTH', maxsplit=1)[1].strip()),
                              sim_version_low=int(sim_versions_str[0]),
                              sim_version_high=int(sim_versions_str[1]))


def parse_component_list(path_to_component_list_txt: Pathlike='https://lookup.x-plane.com/_lookup_mobile_/component_list.txt') -> List[ComponentBlock]:
    try:
        component_list = read_from_web_or_disk(path_to_component_list_txt)
    except URLError as e:
        iphone_repo_root = Path(__file__).parent.parent.parent
        fallback_path = iphone_repo_root / 'resources/common_ios/config/component_list.txt'
        logging.warning(f'Failed to read component list from the web; falling back to local copy at {fallback_path}')
        component_list = read_from_web_or_disk(fallback_path)
    component_token = 'COMPONENT '
    skipped_header = component_token + component_list.split(component_token, maxsplit=1)[1]
    nuked_end = skipped_header.split('ENDOFLIST')[0]
    return [ComponentBlock.from_str(component_token + block) for block in nuked_end.split(component_token) if block]

def component_list_version(path_to_component_list_txt: Pathlike='https://lookup.x-plane.com/_lookup_mobile_/component_list.txt') -> int:
    next_line_is_version = False
    for line in read_from_web_or_disk(path_to_component_list_txt).splitlines():
        if line.rstrip() == 'COMPONENTS':
            assert not next_line_is_version
            next_line_is_version = True
        elif next_line_is_version:
            return int(line)
    raise RuntimeError('Failed to parse component_list.txt version')


def component_versions(components: Iterable[ComponentBlock]) -> Dict[str, List[int]]:
    return {component.component_name: component.manifest_versions
            for component in components}


ManifestHistory = namedtuple('ManifestHistory', ['version'])  # the most *recent* manifest version which touched this file for a modification or delete

@dataclass
class ManifestEntry:
    hash: str
    in_zip: Optional[Path]=None  # None if this is a RAWFILE, or the path of the ZIP this is contained in

@dataclass(frozen=True)
class ComponentManifest:
    """Represents the directory.txt manifest for a component, with both the hashes of current files and the file history"""
    version: int
    install_path_prefix: Path
    entries: DefaultDict[Pathlike, List[ManifestEntry]]  # A given path on disk may be in many places in the manifest (included in an arbitrary number of ZIPs)
    history: Dict[Pathlike, ManifestHistory]
    zips: Dict[Path, str]  # associates ZIP paths with their hash

    def all_paths_all_entries(self) -> List[Tuple[Path, ManifestEntry]]:
        """Flattens the entries dict to give you an iterable of all paths on disk and all their corresponding manifest entries"""
        return [(Path(path), entry)
                for path, locations in self.entries.items()
                for entry in locations]

    # I'm sorry to whomever needs to maintain this...including you future-Chris...but for some reason I found it easier
    # to use REGEX to parse this manifest file than normal string utilities and so....here we are. I will say, 99% of the
    # matching is REGEX 101 with two exceptions:
    #   1) Matching floating point values = ([+-]?(?:[0-9]*[.])?[0-9]+)
    #   2) Matching space-escaped strings like our paths which may have Earth\ Nav\ Data for example. We don't want to see those spaces as whitespace and so we have = ((?:[^\\\s]|\\.)+)
    # Feel free to insult and scathe me for it but I'm at least making SOME attempt to document this so...I'm not a complete asshole.
    @classmethod
    def from_file(cls, manifest_file_path_or_url: Optional[Pathlike]) -> Optional['ComponentManifest']:
        import os
        import re

        prev_manifest_version = -1
        install_path_prefix = ""
        entries = defaultdict(list)
        history = dict()
        zips = dict()

        if manifest_file_path_or_url:
            most_recent_zip: Optional[Path] = None
            for line in read_from_web_or_disk(manifest_file_path_or_url).splitlines():
                # Look at each line for the version number. Until we find it, we don't care about anything else!
                if prev_manifest_version == -1:
                    match_obj = re.match(r'^MANIFEST_VERSION\s+([0-9]+)\s*$', str(line))
                    if match_obj:
                        prev_manifest_version = int(match_obj.group(1))
                        continue
                else:
                    line.strip()
                    # Now look at each line and see if it's an install path prefix
                    if not install_path_prefix and line.startswith("INSTALL_PATH_PREFIX"):
                        match_obj = re.match(r'^INSTALL_PATH_PREFIX\s+(.*)', str(line))
                        if match_obj:
                            install_path_prefix = cls.unescape_spaces(str(match_obj.group(1)))
                            continue
                    elif line.startswith("ZIP") or line.startswith("ZIPFILE") or line.startswith("RAWFILE"):
                        # Check for RAWFILE line
                        match_obj = re.match(r'^RAWFILE\s+([-+]?\d+)\s+([-+]?\d+)\s+([-+]?\d+)\s+([-+]?\d+)\s+(\S+)\s+([+-]?(?:[0-9]*[.])?[0-9]+)\s+(\S+)\s+((?:[^\\\s]|\\.)+)\s+((?:[^\\\s]|\\.)+)', str(line))
                        if match_obj and len(match_obj.groups()) == 9:
                            path = cls.unescape_spaces(os.path.join(install_path_prefix, match_obj.group(8)))
                            assert all(entry.in_zip for entry in entries[path]), f'Duplicated raw file {path}'
                            entries[path].append(ManifestEntry(hash=match_obj.group(7)))
                            continue

                        # Check for ZIP line
                        match_obj = re.match(r'^ZIP\s+([+-]?(?:[0-9]*[.])?[0-9]+)\s+(\S+)\s+((?:[^\\\s]|\\.)+)\s+((?:[^\\\s]|\\.)+)', str(line))
                        if match_obj and len(match_obj.groups()) == 4:
                            most_recent_zip = Path(install_path_prefix) / cls.unescape_spaces(match_obj.group(3))
                            zips[most_recent_zip] = match_obj.group(2)
                            continue

                        # Check for ZIPFILE line
                        match_obj = re.match(r'^ZIPFILE\s+([-+]?\d+)\s+([-+]?\d+)\s+([-+]?\d+)\s+([-+]?\d+)\s+(\S+)\s+([+-]?(?:[0-9]*[.])?[0-9]+)\s+(\S+)\s+(.+)', str(line))
                        if match_obj and len(match_obj.groups()) == 8:
                            assert most_recent_zip, 'This ZIPFILE does not seem to be contained in a ZIP...?'
                            path = cls.unescape_spaces(os.path.join(install_path_prefix, match_obj.group(8)))
                            assert not any(mfst_entry.in_zip == most_recent_zip for mfst_entry in entries[path]), f'File {path} must be unique within the ZIP {most_recent_zip}'
                            entries[path].append(ManifestEntry(hash=match_obj.group(7), in_zip=most_recent_zip))
                            continue

                        raise RuntimeError("We either found a mal-formed manifest line, or this parser has a bug. The line was:\n" + line)
                    elif line.startswith("FILE_HISTORY"):
                        match_obj = re.match(r'^FILE_HISTORY\s+([0-9]+)\s+(.+)', str(line))
                        if match_obj and len(match_obj.groups()) == 2:
                            path = os.path.join(match_obj.group(2))
                            assert path not in history, f'Founnd duplicate history entry for {path}\nHistory entry should only be the most *recent* manifest version which touched this file for a modification or delete.'
                            history[path] = ManifestHistory(int(match_obj.group(1)))
                            continue
            return cls(prev_manifest_version, Path(install_path_prefix), entries, history, zips)
        else:  # no file given
            return None

    @classmethod
    def from_file_with_next_version(cls, manifest_file_path_or_url: Optional[Pathlike]) -> Tuple[Optional['ComponentManifest'], int]:
        out_manifest = cls.from_file(manifest_file_path_or_url)
        next_version = out_manifest.version + 1 if out_manifest else 1
        return out_manifest, next_version

    @staticmethod
    def unescape_spaces(s):
        return str(s).replace("\\ ", " ")


