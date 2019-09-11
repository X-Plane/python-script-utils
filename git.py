#!/usr/bin/env python3
"""A wrapper for commandline Git tools"""

import logging
from pathlib import Path
from subprocess import CalledProcessError
from typing import List, Optional, FrozenSet

from utils.data_processing import checked_subprocess, remove_none


def git(*args, **kwargs) -> str:
    try:
        result = checked_subprocess(['git'] + list(args), **kwargs)
    except CalledProcessError as e:
        logging.error(e.args)
        logging.error(e.stderr)
        raise e
    return result.stdout if result.stdout else result.stderr


def git_modified_files(from_commit: str, to_commit: str) -> List[Path]:
    def get_modified_path(status_and_name: str) -> Optional[Path]:
        """
        Returns the path relative to the repo root (or none, if this status doesn't represent a modification).

        Examples of what status_and_name might look like:
        M       _converters_/ObjConverter
        A       resources/android/library/scenery_packs/sim objects/apt_vehicles/pushback/GT110_NML.etc
        R100    setup_git.sh    scripts/setup_git.sh
        D       resources/common_ios/apt_nav_dat/earth_awy.dat
        """
        if status_and_name[0] == 'M':
            return Path(status_and_name.replace('M', '', 1).strip())
        else:
            return None

    return remove_none(
        map(get_modified_path,
            git('diff', '--name-status', from_commit, to_commit).splitlines(keepends=False))
    )


def git_current_branch() -> str:
    return git('rev-parse', '--abbrev-ref', 'HEAD').strip()


def git_all_known_tags() -> FrozenSet[str]:
    return frozenset(git('tag').strip().splitlines(keepends=False))

def git_current_tags() -> List[str]:
    return git_tags_for_commit('HEAD')

def git_tags_for_commit(sha_or_name: str) -> List[str]:
    return git('tag', '-l', '--points-at', sha_or_name).strip().split()

def git_create_tag(new_tag: str, capture_stdout: bool=True):
    git('tag', new_tag, capture_stdout=capture_stdout)
