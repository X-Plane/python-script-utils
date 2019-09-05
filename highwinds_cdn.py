#!/usr/bin/env python3
import os
from enum import Enum

# Tyler says: The StrikeTracker interface doesn't allow us to just pass a stinking username & password
#             with every request... instead, we have to first make a request (WITH THE USERNAME & PASSWORD)
#             to get a "token"... then we send that *token* with future requests.
#             Note though, that unlike a goddamn username & password, this token will expire in an hour.
#             We'll have to add *additional* complexity to the script if we ever want sessions longer than that.
from getpass import getpass
from pathlib import Path

import requests

from utils.files import Pathlike

global cdn_token
cdn_token = None

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

    def purge_status(self, account_hash, job_id):
        status_response = requests.get(self.base_url + ('/api/v1/accounts/%s/purge/%s' % (account_hash, job_id,)), headers={
            'Authorization': 'Bearer %s' % self.token,
            })
        if 'progress' not in status_response.json():
            raise RuntimeError('Could not fetch purge status', status_response)
        return float(status_response.json()['progress'])


def mobile_abs_server_path(secured_or_unsecured: CdnServer, rel_path: Pathlike=Path('')):
    subdir = 'mobile_unsecured' if secured_or_unsecured == CdnServer.MobileUnsecured else 'mobile_secured'
    return (Path('/var/www/cdn-root/content') / subdir) / rel_path


def flush_cdn_cache(server: CdnServer, mobile_abs_path: Pathlike='/', recursive: bool=True):
    global cdn_token
    client = StrikeTrackerClient(token=cdn_token)
    if not client.token:
        try:
            password = os.environ['HIGHWINDS']
        except KeyError:
            password = getpass('Highwinds Password: ').strip()
        cdn_token = client.create_token('austin@x-plane.com', password, 'mobile.x-plane.com')

    assert str(mobile_abs_path).startswith('/')
    client.purge(server.value, ["http://cds.j4b5j9p4.hwcdn.net%s" % mobile_abs_path], recursive)
