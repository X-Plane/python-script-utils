import logging
from dataclasses import dataclass
from urllib.error import URLError
from pathlib import Path
from typing import List, Iterable, Dict
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



