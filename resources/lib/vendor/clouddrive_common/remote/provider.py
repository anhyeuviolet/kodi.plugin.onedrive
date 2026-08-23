#-------------------------------------------------------------------------------
# Copyright (C) 2017 Carlos Guzman (cguZZman) carlosguzmang@protonmail.com
#
# This file is part of Cloud Drive Common Module for Kodi
#
# Cloud Drive Common Module for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Cloud Drive Common Module for Kodi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------

import json
import re
import urllib.parse

from resources.lib import auth_context
from resources.lib.auth import device_code, refresh, store
from resources.lib.auth.lock import RefreshLock
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils, \
    RequestException
from resources.lib.vendor.clouddrive_common.remote.oauth2 import OAuth2
from resources.lib.vendor.clouddrive_common.remote.request import Request
from resources.lib.vendor.clouddrive_common.utils import Utils
from urllib.error import HTTPError


# The setting that lets one installation use its own application registration.
# It is an escape hatch for a tenant that blocks the built-in one, nothing more:
# it changes WHICH application asks for the credential, never WHERE the
# credential is sent. The authority is `device_code.AUTHORITY` and it is not
# configurable and must never become configurable -- a setting that redirected
# where a token is sent would be a setting that exfiltrates it (AUTH-19).
CLIENT_ID_SETTING = 'client_id'

# The shape a Microsoft application identifier has: a canonical GUID. Validated
# rather than trusted, and validated silently -- a user who mistypes into an
# expert-level text box should get the built-in registration back, not an add-on
# that will not sign in and does not say why.
CLIENT_ID_PATTERN = re.compile(
    r'\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z')

# The device-code request happens once, with the user watching a progress
# dialog. Two attempts five seconds apart bounds it at 65 seconds; the
# transport's own default of four attempts with doubling delays would bound it
# at 155, which on a marginal connection is two and a half minutes of a dialog
# that says nothing.
DEVICE_CODE_TRIES = 2
DEVICE_CODE_DELAY_SECONDS = 5
DEVICE_CODE_BACKOFF = 1

# One poll is one attempt, deliberately. The sign-in loop IS the retry: it comes
# back every `interval` seconds for as long as the code lives, and a transport
# that retried underneath it would poll faster than the interval the server
# asked for, which is what earns a slow_down.
POLL_TRIES = 1

# The form encoding every one of these endpoints expects. RFC 6749 section 4.1.3
# and RFC 8628 section 3.1 both specify it; the endpoints answer JSON but they
# are not asked in it.
FORM_CONTENT_TYPE = 'application/x-www-form-urlencoded'


class ReauthorisationRequired(Exception):
    """The stored grant is finished and only a new sign-in can replace it.

    Distinct from a transport failure on purpose, and the distinction is the
    whole of Pitfall E: a refresh that fails because the Wi-Fi was not up yet
    must not sign anybody out. `resources/lib/auth/refresh.py` draws that line
    -- including the case where an `invalid_grant` means "another contender
    spent this token a moment ago" rather than "this grant is dead" -- and this
    exception is raised only for the outcome it names NEEDS_REAUTHORISATION.
    """


def resolve_client_id():
    """The application identifier to ask with.

    The embedded constant, overridden by the expert-level setting when that
    setting holds a well-formed identifier. Anything else falls back silently.
    """
    from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
    try:
        configured = Utils.str(KodiUtils.get_addon_setting(CLIENT_ID_SETTING)).strip()
    except Exception:
        # A setting that does not exist yet, or an add-on handle that could not
        # be opened. Neither is a reason to fail to sign in.
        return device_code.CLIENT_ID
    if configured and CLIENT_ID_PATTERN.match(configured):
        return configured
    return device_code.CLIENT_ID


class Provider(OAuth2):
    name = ''
    source_mode = False
    download_requires_auth = False
    _account_manager = None
    _driveid = None


    def __init__(self, name, source_mode = False):
        self.name = name
        self.source_mode = source_mode

    # -- the HTTP port the pure package takes -----------------------------
    #
    # `post(url, fields) -> (status, body)`, with `body` already parsed. That
    # one callable is the entire coupling between resources/lib/auth/ and the
    # network, and building it here is what keeps that package free of sockets.

    def _post_port(self, tries=None, delay=None, backoff=None,
                   request_params=None):
        request_params = self._stop_retrying_a_settled_answer(request_params)

        def post(url, fields):
            request = Request(url, urllib.parse.urlencode(fields),
                              {'content-type': FORM_CONTENT_TYPE},
                              tries=tries, delay=delay, backoff=backoff,
                              **request_params)
            try:
                request.request()
            except RequestException:
                # An HTTP 400 carrying a JSON body is the protocol speaking,
                # not a failure: RFC 6749 section 5.2 defines every error
                # response that way, and `authorization_pending` -- the
                # ordinary state while the user types the code into their
                # phone -- arrives as one. The transport raises on it all the
                # same, so the answer is read off the request rather than off
                # the return value. Only a call that produced no HTTP response
                # at all is re-raised, because that one really is a transport
                # failure and the callers treat it as such.
                if request.response_code is None:
                    raise
            return request.response_code, self._parse_body(request.response_text)

        return post

    @staticmethod
    def _stop_retrying_a_settled_answer(request_params):
        """Wrap the transport's exception hook so a 4xx is not retried.

        A 4xx from the token endpoint is the protocol's final word: an expired
        device code, a rejected one, a refresh token that has already been
        spent. Retrying it re-sends a credential that has just been refused and
        buys a delay under the refresh lock for an answer that will not change.
        429 is the exception -- that is a request to come back, not a refusal --
        and so is every 5xx.

        This only ever SHORTENS a call, which is why it cannot disturb the
        worst-case arithmetic the lock lifetime is set against.
        """
        request_params = dict(Utils.default(request_params, {}))
        original = Utils.get_safe_value(request_params, 'on_exception', None)

        def on_exception(request, exception):
            http = ExceptionUtils.extract_exception(exception, HTTPError)
            if http and 400 <= http.code < 500 and http.code != 429:
                request.tries = request.current_tries
            if original:
                original(request, exception)

        request_params['on_exception'] = on_exception
        return request_params

    @staticmethod
    def _parse_body(text):
        """The response as a dictionary, or the non-JSON sentinel.

        These endpoints answer in JSON and only in JSON, so anything else did
        not come from the protocol -- it came from a captive portal, a proxy
        error page or a truncated read. `device_code.poll_once` turns the
        sentinel into a TransportError rather than a classification, which is
        what stops a hotel Wi-Fi from reading as a revoked grant.
        """
        try:
            body = json.loads(Utils.default(text, '{}'))
        except Exception:
            return {'error': device_code.NON_JSON_ERROR}
        if not isinstance(body, dict):
            return {'error': device_code.NON_JSON_ERROR}
        return body

    # -- the protocol, delegated ------------------------------------------

    def request_device_code(self, request_params=None):
        """Ask the identity provider for a device code.

        Everything the dialog shows -- the code, the address, the expiry, the
        interval -- comes out of the returned dictionary and none of it is
        constructed here.
        """
        return device_code.request_device_code(
            self._post_port(tries=DEVICE_CODE_TRIES,
                            delay=DEVICE_CODE_DELAY_SECONDS,
                            backoff=DEVICE_CODE_BACKOFF,
                            request_params=request_params),
            resolve_client_id())

    def poll_for_token(self, code, request_params=None):
        """Exchange the device code once. Returns (state, payload).

        One request, classified. The caller owns the loop, the interval and the
        deadline, which is what keeps the abort check in the Kodi-side loop
        where it belongs.
        """
        return device_code.poll_once(
            self._post_port(tries=POLL_TRIES,
                            delay=DEVICE_CODE_DELAY_SECONDS,
                            backoff=DEVICE_CODE_BACKOFF,
                            request_params=request_params),
            resolve_client_id(), code)

    def configure(self, account_manager, driveid):
        self._account_manager = account_manager
        self._driveid = driveid

    def validate_configuration(self):
        if not self._account_manager:
            raise Exception('Account Manager not defined')
        if not self._driveid:
            raise Exception('DriveId not defined')

    def _account_from_manager(self):
        self.validate_configuration()
        return self._account_manager.get_by_driveid('account', self._driveid)

    def _drive_from_manager(self):
        self.validate_configuration()
        return self._account_manager.get_by_driveid('drive', self._driveid)

    def _account_key(self):
        """The key this account's files on disk are named by.

        The subject claim from the identity token, recorded as the account
        record's id when the account was added. It is pairwise and
        per-application, and `store.validate_account_key` rejects anything that
        would not be safe in a filename rather than sanitising it.
        """
        return Utils.str(self._account_from_manager()['id'])

    # -- the token-store seam ---------------------------------------------
    #
    # Two methods, and they are the only two places in the add-on that read or
    # write a credential. Everything above them -- the OAuth2 reader's expiry
    # check, the mid-request refresh, the sign-in flow -- goes through these,
    # and they go to the per-account file rather than into the account record.
    # That is the seam the rotation, lock and adoption tests already exercise.

    def get_access_tokens(self):
        """This account's stored token blob.

        `{}` before the first sign-in, which `OAuth2._validate_access_tokens`
        turns into its own "not valid" failure -- and that is the correct
        answer, because there is no account to make a request for.
        """
        return store.read(store.token_path(auth_context.profile_path(),
                                           self._account_key()))

    def persist_access_tokens(self, access_tokens):
        self.save_tokens(self._account_key(), access_tokens)

    def save_tokens(self, account_key, token_response):
        """Merge `token_response` onto what is stored and write it, under lock.

        Through `store.merge_token_response` and never around it. A response
        that omits `refresh_token` means keep the previous one; a blob written
        from the response alone is an add-on that works perfectly until the
        stored refresh token reaches its ninety-day lifetime, and then stops
        for every installation on the same day (AUTH-12).
        """
        profile = auth_context.profile_path()
        store.accounts_dir(profile, create=True)
        token_file = store.token_path(profile, account_key)
        lock = self._lock_for(profile, account_key)
        if not lock.acquire(refresh.ACQUIRE_TIMEOUT_SECONDS):
            # Somebody else holds it, which means somebody else is mid-refresh
            # and is about to write a NEWER blob than this one. Writing over
            # them would replace a rotated refresh token with the one it
            # replaced. Doing nothing is the correct answer.
            auth_context.log('token store: lock held elsewhere, not writing')
            return
        try:
            store.write(token_file, store.merge_token_response(
                store.read(token_file), token_response))
        finally:
            lock.release()

    @staticmethod
    def _lock_for(profile, account_key):
        return RefreshLock(store.lock_path(profile, account_key),
                           auth_context.session_id(), auth_context.wait)

    def get_change_token(self):
        return Utils.get_safe_value(self._drive_from_manager(), 'change_token')

    def refresh_access_tokens(self, request_params=None):
        """Spend the stored refresh token for a new pair, under the lock.

        The whole of the race lives in `resources/lib/auth/refresh.py`; what is
        here is the Kodi half it cannot have -- the resolved profile path, the
        session identifier, the abort-aware wait, and the transport.

        THE TRANSPORT'S PROFILE IS NOT A DETAIL. `refresh.REQUEST_TRIES`,
        `refresh.REQUEST_DELAY_SECONDS` and `refresh.REQUEST_BACKOFF` bound one
        refresh at 2 * 30 + 5 = 65 seconds, and `RefreshLock.LIFETIME_SECONDS`
        is 90 because of that arithmetic and nothing else. On the transport's
        own defaults the worst case is 155 seconds, and a refresh that outlives
        the lock lifetime is a live lock that a second contender is entitled to
        break -- the exact race the lock exists to prevent. The two constants
        move together or not at all;
        tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile
        is what stops them moving apart.
        """
        profile = auth_context.profile_path()
        account_key = self._account_key()

        result = refresh.refresh(
            profile, account_key, self._lock_for(profile, account_key),
            self._post_port(tries=refresh.REQUEST_TRIES,
                            delay=refresh.REQUEST_DELAY_SECONDS,
                            backoff=refresh.REQUEST_BACKOFF,
                            request_params=request_params),
            auth_context.wait,
            client_id=resolve_client_id(), log=auth_context.log)

        if result.outcome == refresh.NEEDS_REAUTHORISATION:
            raise ReauthorisationRequired(
                'the stored grant for this account can no longer be refreshed')
        if result.outcome != refresh.SUCCEEDED:
            # Transient. Saying so rather than raising a bare Exception is what
            # lets a caller tell "try again later" from "sign in again".
            raise RequestException(
                'the token endpoint could not be reached; the grant is intact',
                None, 'refresh_access_tokens', '<transient>')
        return result.blob

    def persist_change_token(self, change_token):
        drive = self._drive_from_manager()
        drive['change_token'] = change_token
        self._account_manager.save_drive(drive)

    def get_account(self, request_params=None, access_tokens=None):
        raise NotImplementedError()

    def get_drives(self, request_params=None, access_tokens=None):
        raise NotImplementedError()

    def get_drive_type_name(self, drive_type):
        return drive_type

    def cancel_operation(self):
        return False

    def changes(self):
        return []
