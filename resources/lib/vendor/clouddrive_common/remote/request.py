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

from resources.lib.vendor.clouddrive_common.exception import RequestException
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.utils import Utils
from http.cookiejar import CookieJar
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
from urllib.error import HTTPError
import urllib


class Request(object):
    _DEFAULT_RESPONSE = '{}'
    # Bounds the single outbound call below. Without it the call inherits the
    # global socket default of none and can block forever; on marginal Android
    # TV Wi-Fi that is a spinner the user cannot escape.
    #
    # The value applies per socket operation, not to a whole transfer: it bounds
    # how long one read may block, not how long a large file may take. That is
    # why one constant correctly serves both the metadata path and the chunked
    # download path further down, which share this one call site.
    #
    # Unmeasured. 15-30 seconds is the recommended range for metadata calls;
    # too low causes spurious failures on slow Wi-Fi, too high reproduces the
    # hang this exists to remove. Confirm on a real device before relying on it.
    #
    # Worst-case wall time of the retry loop below is tries * this timeout plus
    # the waits between attempts. At this class's defaults (tries=4, delay=5,
    # backoff=2) that is 4*30 + 5 + 10 + 20 = 155 seconds. Bounding it is not
    # this change's job; the wait goes through an injected function and belongs
    # with the abort-aware sleep work.
    HTTP_TIMEOUT_SECONDS = 30
    DOWNLOAD_CHUNK_SIZE = 16 * 1024
    download_progress = 0
    url = None
    data = None
    headers = None
    tries = 1
    current_tries = 0
    delay = 0
    current_delay = 0
    backoff = 0
    before_request = None
    on_exception = None
    on_failure = None
    on_success = None
    on_complete = None
    exceptions = None
    cancel_operation = None
    waiting_retry = None
    wait = None
    read_content = True
    success = False
    response_url = None
    response_code = None
    response_info = None
    response_text = None
    response_cookies = None
    
    def __init__(self, url, data, headers=None, tries=4, delay=5, backoff=2, exceptions=None, \
                 before_request=None, on_exception=None, on_failure=None, on_success=None, on_complete=None, on_update_download=None, \
                 cancel_operation=None, waiting_retry=None, wait=None, read_content=True, download_path=None):
        self.url = url
        if isinstance(data, str):
            self.data = Utils.encode(data)
        else:
            self.data = data
        self.headers = headers
        self.tries = tries
        self.current_tries = tries
        self.delay = delay
        self.current_delay = delay
        self.backoff = backoff
        self.before_request = before_request
        self.on_exception = on_exception
        self.on_failure = on_failure
        self.on_success = on_success
        self.on_complete = on_complete
        self.exceptions = exceptions
        self.cancel_operation = cancel_operation
        self.waiting_retry = waiting_retry
        self.wait = wait
        self.read_content = read_content
        self.download_path = download_path
        self.on_update_download = on_update_download
    
    def get_url_for_report(self, url):
        index = url.find('access_token=')
        if index > -1:
            url_report = url[:index + 13] + '*removed*'
            index = url.find('&', index + 1)
            if index > -1:
                url_report += url[index:]
            return url_report
        # The clause above only knows one field name and only the first
        # occurrence of it. A query string can carry any of the five, so it
        # goes through the same redactor the bodies do.
        return self.get_body_for_report(url)
    
    @classmethod
    def get_headers_for_report(cls, headers):
        """The headers with the bearer token taken out.

        A classmethod, and total in `headers`, for the same reason
        `get_body_for_report` is: the OAuth2 layer reports a failure before any
        Request exists to report it through, and one of its call sites has no
        headers to speak of and passes a plain string instead. Iterating that
        would report a dictionary of single characters, and building a report
        is not allowed to be the thing that goes wrong.
        """
        if not isinstance(headers, dict):
            return headers
        headers_report = {}
        for header in headers:
            if header == 'authorization':
                headers_report[header] = '*removed*'
            else:
                headers_report[header] = headers[header]
        return headers_report

    # -- credential redaction in the report ------------------------------
    #
    # The bearer header and one query parameter were already covered. Neither
    # is where the device-code flow puts its credentials: a token exchange
    # sends the device code in a form BODY and gets three tokens back in a JSON
    # body, and both bodies were being concatenated into a report string that
    # goes straight to the Kodi log.
    #
    # A Kodi log is a file users paste into forum posts and attach to issues
    # verbatim. A successful token response IS the credential -- there is
    # nothing else to steal -- and the two codes are worth a session to whoever
    # reads them before the user has finished typing them into their phone.
    #
    # All five, in both directions. Covering four is publishing the fifth.
    REDACTED_FIELDS = ('access_token', 'refresh_token', 'id_token',
                       'device_code', 'user_code')

    # Enough to correlate two log lines -- did the stored token change between
    # refreshes -- and not enough to use. The same eight the refresh module's
    # fingerprint keeps, so the two are comparable by eye.
    REDACTED_PREFIX_CHARACTERS = 8
    REDACTED_MARKER = '...*removed*'

    # Two shapes, because these bodies come in two: JSON on the way back and
    # form encoding on the way out. Both are built from REDACTED_FIELDS rather
    # than written out, so adding a field name to the tuple above is the whole
    # of adding it to the redactor.
    _REDACT_ALTERNATION = '|'.join(re.escape(f) for f in REDACTED_FIELDS)
    _REDACT_JSON = re.compile(
        r'("(?:%s)"\s*:\s*")([^"]*)(")' % _REDACT_ALTERNATION)
    _REDACT_FORM = re.compile(
        r'((?:^|[?&])(?:%s)=)([^&\s"\']*)' % _REDACT_ALTERNATION)

    @classmethod
    def _keep_prefix(cls, value):
        """At most eight leading characters, and nothing at all if that would
        be most of the value.

        The three tokens are hundreds of characters long, so eight correlates
        two log lines and discloses nothing usable. `user_code` is nine
        characters. Keeping eight of those nine is not a fingerprint, it is the
        code with a typo -- and it is live for as long as the dialog is on
        screen. So a value that is not at least twice the prefix goes entirely.
        """
        if not value:
            return value
        if len(value) <= 2 * cls.REDACTED_PREFIX_CHARACTERS:
            return cls.REDACTED_MARKER
        return value[:cls.REDACTED_PREFIX_CHARACTERS] + cls.REDACTED_MARKER

    @classmethod
    def get_body_for_report(cls, body):
        """A request or response body with every credential field cut short.

        Never raises. This runs inside the logging path, including the logging
        path of a failure, and an exception thrown while reporting an exception
        loses the original -- so an unreadable body reports as unreadable
        rather than taking the report down with it.
        """
        if body is None:
            return Utils.str(body)
        try:
            text = Utils.str(body)
        except Exception:
            return '<possible binary content>'
        text = cls._REDACT_JSON.sub(
            lambda m: m.group(1) + cls._keep_prefix(m.group(2)) + m.group(3),
            text)
        return cls._REDACT_FORM.sub(
            lambda m: m.group(1) + cls._keep_prefix(m.group(2)), text)

    def request(self):
        self.response_text = self._DEFAULT_RESPONSE
        if not self.exceptions:
            self.exceptions = Exception
        if not self.wait:
            self.wait = time.sleep
        if not self.headers:
            self.headers = {}
        
        for i in range(self.tries):
            self.current_tries = i + 1
            if self.before_request:
                self.before_request(self)
            if self.cancel_operation and self.cancel_operation():
                break
            request_report = 'Request URL: ' + self.get_url_for_report(self.url)
            request_report += '\nRequest data: ' + self.get_body_for_report(self.data)
            request_report += '\nRequest headers: ' + Utils.str(self.get_headers_for_report(self.headers))
            response_report = '<response_not_set>'
            response = None
            rex = None
            download_file = None
            try:
                Logger.debug(request_report)
                req = urllib.request.Request(self.url, self.data, self.headers)
                response = urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT_SECONDS)
                self.response_code = response.getcode()
                self.response_info = response.info()
                self.response_url = response.geturl()
                cookiejar = CookieJar()
                cookiejar._policy._now = cookiejar._now = int(time.time())
                self.response_cookies = cookiejar.make_cookies(response, req)
                if self.read_content:
                    if self.download_path:
                        self.response_text = 'Downloading to: ' + self.download_path + '... '
                        download_file = KodiUtils.file(self.download_path, 'wb')
                        self.download_progress = 0
                        while True:
                            chunk = response.read(self.DOWNLOAD_CHUNK_SIZE)
                            if not chunk:
                                break
                            download_file.write(chunk)
                            self.download_progress += self.DOWNLOAD_CHUNK_SIZE
                            if self.on_update_download:
                                self.on_update_download(self)
                        self.response_text += ' OK.'
                    else:
                        self.response_text = response.read()
                content_length = self.response_info.get('content-length', -1)
                response_report = '\nResponse Headers:\n%s' % Utils.str(self.response_info)
                response_report += '\nResponse (%d) content-length=%s, len=<%s>:\n' % (self.response_code, content_length, len(self.response_text),)
                try:
                    response_report += self.get_body_for_report(self.response_text)
                except:
                    response_report += '<possible binary content>'
                self.success = True
                break
            except self.exceptions as e:
                Logger.debug('Exception...')
                root_exception = e
                response_report = '\nResponse <Exception>: ' 
                if isinstance(e, HTTPError):
                    self.response_code = e.code
                    self.response_text = Utils.str(e.read())
                    # This is the one that matters most. A failing token
                    # exchange answers 400 with a JSON body, and that body is
                    # what an error report carries into the log.
                    response_report += self.get_body_for_report(self.response_text)
                else:
                    response_report += Utils.str(e)
                rex = RequestException(Utils.str(e), root_exception, request_report, response_report)
            finally:
                try:
                    if download_file:
                        download_file.close()
                    Logger.debug(response_report)
                except:
                    Logger.debug('unable to print response_report')
                if response:
                    response.close()
            if rex:
                if self.on_exception:
                    Logger.debug('calling self.on_exception...')
                    self.on_exception(self, rex)
                if self.cancel_operation and self.cancel_operation():
                    break
                Logger.debug('current_tries: ' + str(self.current_tries) + ' maximum tries: ' + str(self.tries) + ' i: ' + str(i))
                if self.current_tries == self.tries:
                    Logger.debug('max retries reached')
                    if self.on_failure:
                        self.on_failure(self)
                    if self.on_complete:
                        self.on_complete(self)
                    Logger.debug('Raising exception...')
                    raise rex
                current_time = time.time()
                max_waiting_time = current_time + self.current_delay
                Logger.debug('current_delay: ' + str(self.current_delay) + ' seconds. Waiting...')
                while (not self.cancel_operation or not self.cancel_operation()) and max_waiting_time > current_time:
                    remaining = round(max_waiting_time-current_time)
                    if self.waiting_retry:
                        Logger.debug('calling self.waiting_retry...')
                        self.waiting_retry(self, remaining)
                    self.wait(1)
                    current_time = time.time()
                Logger.debug('Done waiting.')
                self.current_delay *= self.backoff
            
        if self.success and self.on_success:
            self.on_success(self)
        if self.on_complete:
            self.on_complete(self)
        return self.response_text
        
    def request_json(self):
        return json.loads(Utils.default(self.request(), self._DEFAULT_RESPONSE))

    def get_response_text_as_json(self):
        return json.loads(Utils.default(self.response_text, self._DEFAULT_RESPONSE))
