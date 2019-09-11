#!/usr/bin/env python3
import logging
import os
from enum import Enum
from getpass import getpass
from pathlib import Path
from time import sleep
from typing import Iterable, Union, List, Collection

import requests  # TODO: Remove dependency for downstream clients
from utils.files import Pathlike

global cdn_token
try:
    cdn_token = os.environ['HIGHWINDS_TOKEN']
except KeyError:
    cdn_token = None  # we'll generate a temporary token via username & password on our first interaction with the CDN


class CdnServer(Enum):
    MobileSecure = 'b3y9j3a5'
    MobileUnsecured = 'j4b5j9p4'

    def for_component_list(self):
        return 'SERVER_SECURE' if self is CdnServer.MobileSecure else 'SERVER_UNSECURE'

    @staticmethod
    def from_component_list_id(server_id: str):
        return CdnServer.MobileSecure if server_id == 'SERVER_SECURE' else CdnServer.MobileUnsecured


class StrikeTrackerClient:
    """Copied with minor modifications from the no-longer-maintained official client: https://github.com/Highwinds/striketracker"""
    def __init__(self, base_url='https://striketracker.highwinds.com', account_hash='c7c3x3s9', token=None):
        self.base_url = base_url
        self.token = token
        self.account_hash = account_hash

    def create_token(self, username, password, application=None):
        if application is None:
            application = 'StrikeTracker Python client'

        # Grab an access token to use to fetch user
        response = requests.post(self.base_url + '/auth/token', data={
            "username": username, "password": password, "grant_type": "password"
        }, headers={
            'User-Agent': application
        })
        auth = response.json()
        if 'access_token' not in auth:
            raise RuntimeError('Could not fetch access token', response)
        access_token = auth['access_token']

        # Grab user's id and root account hash
        user_response = requests.get(self.base_url + '/api/v1/users/me', headers={'Authorization': 'Bearer %s' % access_token})
        user = user_response.json()
        if 'accountHash' not in user or 'id' not in user:
            raise RuntimeError('Could not fetch user\'s root account hash', user_response)
        self.account_hash = user['accountHash']
        user_id = user['id']

        # Generate a new API token
        token_response = requests.post(self.base_url + ('/api/v1/accounts/{account_hash}/users/{user_id}/tokens'.format(
            account_hash=self.account_hash, user_id=user_id
        )), json={
            "password": password, "application": application
        }, headers={
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': 'application/json'
        })
        if 'token' not in token_response.json():
            raise RuntimeError('Could not generate API token', token_response)
        self.token = token_response.json()['token']
        return self.token

    def purge(self, urls, recursive=True):
        purge_response = requests.post(f'{self.base_url}/api/v1/accounts/{self.account_hash}/purge', json={
            "list": [{"url": url, "recursive":  recursive}
                     for url in urls]
        }, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.token
        })
        if 'id' not in purge_response.json():
            raise RuntimeError('Could not send purge batch', purge_response)
        return purge_response.json()['id']

    def purge_status_ratio(self, job_id) -> float:
        """Returns the progress as a ratio of the total items to be purged (in the range 0 to 1)"""
        status_response = requests.get(f'{self.base_url}/api/v1/accounts/{self.account_hash}/purge/{job_id}', headers={
            'Authorization': 'Bearer %s' % self.token,
            })
        if 'progress' not in status_response.json():
            raise RuntimeError('Could not fetch purge status', status_response)
        return float(status_response.json()['progress'])


def mobile_abs_server_path(secured_or_unsecured: CdnServer, rel_path: Pathlike=Path('')) -> Path:
    subdir = 'mobile_unsecured' if secured_or_unsecured == CdnServer.MobileUnsecured else 'mobile_secured'
    return (Path('/var/www/cdn-root/content') / subdir) / rel_path


def flush_cdn_cache(server: CdnServer, mobile_abs_paths: Union[Pathlike, Collection[Pathlike]]='/', recursive: bool=True, await_confirmation: bool=False):
    global cdn_token
    client = StrikeTrackerClient(token=cdn_token)
    if not client.token:  # we'll need to generate a temporary token
        cdn_token = client.create_token('austin@x-plane.com', getpass('Highwinds Password: ').strip(), 'mobile.x-plane.com')

    if isinstance(mobile_abs_paths, str) or isinstance(mobile_abs_paths, Path):
        mobile_abs_paths = [mobile_abs_paths]

    assert all(str(path).startswith('/') for path in mobile_abs_paths), 'CDN path was not absolute'
    urls = [f"http://cds.{server.value}.hwcdn.net{path}"
            for path in mobile_abs_paths]
    purge_job_id = client.purge(urls, recursive)
    waited = 0
    ratio_complete = 0
    while await_confirmation and ratio_complete < 0.99:
        ratio_complete = client.purge_status_ratio(purge_job_id)
        sleep(1)
        waited += 1
        if waited > 30 + len(mobile_abs_paths):
            raise TimeoutError(f'CDN cache flushed timed out after {waited} seconds')
        elif waited % 10 == 0:
            logging.info(f'Waiting for purge to complete (currently at {ratio_complete * 100}%, after {waited} seconds waiting)')
    logging.info(f'Purge completed after {waited} seconds')

