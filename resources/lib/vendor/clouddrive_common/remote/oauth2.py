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
import time
import urllib

from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils, RequestException
from resources.lib.vendor.clouddrive_common.remote.request import Request
from resources.lib.vendor.clouddrive_common.utils import Utils
from urllib.error import HTTPError


class OAuth2(object):
    
    def _get_api_url(self):
        raise NotImplementedError()

    def _get_request_headers(self):
        raise NotImplementedError()
    
    def get_access_tokens(self):
        raise NotImplementedError()
    
    def refresh_access_tokens(self, request_params=None):
        raise NotImplementedError()
    
    def persist_access_tokens(self, access_tokens):
        raise NotImplementedError()
    
    def _on_exception(self, request, e, original_on_exception):
        ex = ExceptionUtils.extract_exception(e, HTTPError)
        if ex and ex.code != 503:
            request.tries = request.current_tries
        if original_on_exception and not(original_on_exception is self._on_exception):
            original_on_exception(request, e)
            
    def _wrap_on_exception(self, request_params=None):
        request_params = Utils.default(request_params, {})
        original_on_exception = Utils.get_safe_value(request_params, 'on_exception', None)
        request_params['on_exception'] = lambda request, e: self._on_exception(request, e, original_on_exception)
        return request_params
    
    # The four fields a blob must carry before a request can be built from it.
    # Three are the provider's; `date` is stamped locally by
    # resources/lib/auth/store.merge_token_response, and it is the one the
    # expiry arithmetic in prepare_request reads. Written once, here, so the
    # check and the message it raises cannot disagree about what is required.
    REQUIRED_ACCESS_TOKEN_FIELDS = ('access_token', 'refresh_token',
                                    'expires_in', 'date')

    @classmethod
    def _access_tokens_for_report(cls, access_tokens):
        """Which fields arrived. Never what any of them contains.

        What stood here was `Utils.str(access_tokens)`, and this message is
        carried to a Kodi dialog by CloudDriveAddon._handle_exception as the
        root exception's text -- so a whole token blob, access token and
        refresh token and identity token in the clear, was printed on a
        television. It also reaches the Kodi log, which users paste into forum
        posts verbatim.

        Field NAMES are not credentials and they are the whole of what a
        maintainer needs from this failure: which of the four is missing, and
        what turned up instead. That distinguishes a blob that never went
        through the store's merge (no `date`) from an empty one (no fields at
        all) from a refresh response the provider truncated, which is every
        question this message has ever had to answer.

        Never raises. It runs while reporting a failure, and an exception
        thrown here would replace the original with itself.

        The `_for_report` suffix is load-bearing, not decorative: it is the
        naming convention `Request.get_body_for_report` and
        `Request.get_headers_for_report` already use, and
        tests/test_auth_gates.py::test_no_exception_message_carries_a_credential
        reads it to tell a redacted value from a raw one.
        """
        if not access_tokens:
            return 'no token blob at all'
        try:
            names = sorted(Utils.str(name) for name in access_tokens)
        except Exception:
            return 'a token blob whose field names could not be read'
        return 'fields present: ' + ', '.join(names)

    def _validate_access_tokens(self, access_tokens, url, data, request_headers):
        missing = [field for field in self.REQUIRED_ACCESS_TOKEN_FIELDS
                   if not access_tokens or field not in access_tokens]
        if not missing:
            return
        # Every part of this goes through the transport's own redactor. The
        # request data for a token exchange is a form body carrying the refresh
        # token, the device code and the client id; the URL can carry an
        # access_token parameter; and the headers can carry the bearer. All
        # three were being concatenated in raw (03-08's rule: a value shorter
        # than twice the redaction prefix is dropped entirely rather than
        # half-masked, which is what `_keep_prefix` does).
        raise RequestException(
            'Access tokens provided are not valid: missing '
            + ', '.join(missing) + '; ' + self._access_tokens_for_report(access_tokens),
            None,
            'Request URL: ' + Request.get_body_for_report(url)
            + '\nRequest data: ' + Request.get_body_for_report(data)
            + '\nRequest headers: '
            + Utils.str(Request.get_headers_for_report(request_headers)),
            None)
    
    def _build_url(self, method, path, parameters):
        url = self._get_api_url()
        if re.search("^https?://", path):
            url = path
        else:
            if not (re.search("^\/", path)):
                path = '/' + path
            url += path
        if method == 'get' and parameters:
            url += '?' + parameters
        return url
    
    def prepare_request(self, method, path, parameters=None, request_params=None, access_tokens=None, headers=None):
        parameters = Utils.default(parameters, {})
        access_tokens = Utils.default(access_tokens, {})
        encoded_parameters = urllib.parse.urlencode(parameters)
        url = self._build_url(method, path, encoded_parameters)
        request_params = self._wrap_on_exception(request_params)
        if not headers:
            headers = Utils.default(self._get_request_headers(), {})
        content_type = Utils.get_safe_value(headers, 'content-type', '')
        if content_type == 'application/json':
            data = json.dumps(parameters)
        else:
            data = None if method == 'get' else encoded_parameters
        if not access_tokens:
            access_tokens = self.get_access_tokens()
        self._validate_access_tokens(access_tokens, url, data, headers)
        if time.time() > (access_tokens['date'] + access_tokens['expires_in'] - 600):
            access_tokens.update(self.refresh_access_tokens(request_params))
            self._validate_access_tokens(access_tokens, 'refresh_access_tokens', 'Unknown', 'Unknown')
            self.persist_access_tokens(access_tokens)
        headers['authorization'] = 'Bearer ' + access_tokens['access_token']
        return Request(url, data, headers, **request_params) 
    
    def request(self, method, path, parameters=None, request_params=None, access_tokens=None, headers=None):
        return self.prepare_request(method, path, parameters, request_params, access_tokens, headers).request_json()
    
    def get(self, path, **kwargs):
        return self.request('get', path, **kwargs)
    
    def post(self, path, **kwargs):
        return self.request('post', path, **kwargs)
