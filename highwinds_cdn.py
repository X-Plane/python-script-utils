#!/usr/bin/env python3
import os
from enum import Enum
from getpass import getpass
from pathlib import Path
import requests
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
    def __init__(self, base_url='https://striketracker.highwinds.com', token=None):
        self.base_url = base_url
        self.token = token

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
        account_hash = user['accountHash']
        user_id = user['id']

        # Generate a new API token
        token_response = requests.post(self.base_url + ('/api/v1/accounts/{account_hash}/users/{user_id}/tokens'.format(
            account_hash=account_hash, user_id=user_id
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

    def purge(self, account_hash, urls, recursive=True):
        purge_response = requests.post(self.base_url + ('/api/v1/accounts/%s/purge' % account_hash), json={
            "list": [{"url": url, "recursive":  recursive}
                     for url in urls]
        }, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % self.token
        })
        if 'id' not in purge_response.json():
            raise RuntimeError('Could not send purge batch', purge_response)
        return purge_response.json()['id']

    def purge_status(self, account_hash, job_id) -> float:
        status_response = requests.get(self.base_url + ('/api/v1/accounts/%s/purge/%s' % (account_hash, job_id,)), headers={
            'Authorization': 'Bearer %s' % self.token,
            })
        if 'progress' not in status_response.json():
            raise RuntimeError('Could not fetch purge status', status_response)
        return float(status_response.json()['progress'])


def mobile_abs_server_path(secured_or_unsecured: CdnServer, rel_path: Pathlike=Path('')) -> Path:
    subdir = 'mobile_unsecured' if secured_or_unsecured == CdnServer.MobileUnsecured else 'mobile_secured'
    return (Path('/var/www/cdn-root/content') / subdir) / rel_path


def flush_cdn_cache(server: CdnServer, mobile_abs_path: Pathlike='/', recursive: bool=True):
    global cdn_token
    client = StrikeTrackerClient(token=cdn_token)
    if not client.token:  # we'll need to generate a temporary token
        cdn_token = client.create_token('austin@x-plane.com', getpass('Highwinds Password: ').strip(), 'mobile.x-plane.com')

    assert str(mobile_abs_path).startswith('/'), 'CDN path was not absolute'
    client.purge('c7c3x3s9', [f"http://cds.{server.value}.hwcdn.net{mobile_abs_path}"], recursive)
