#-------------------------------------------------------------------------------
# This file is part of OneDrive for Kodi
#
# OneDrive for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
"""The loopback download service, relaying instead of redirecting.

The vendored `Download` handler answered every request with a 307 to OneDrive's
short-lived download URL, which Kodi then kept using after it expired. This
handler keeps the same addresses (`/download/<driveid>/<item_driveid>/<item_id>/
<name>`) and relays the bytes itself; `resources/lib/streaming.py` explains the
failure and the recovery.

It replaces the vendored handler from this repository's own `service.py`, so the
vendored file is unchanged.
"""

import threading
import time
import urllib.request

from resources.lib import streaming
from resources.lib.vendor.clouddrive_common.account import AccountManager
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils
from resources.lib.vendor.clouddrive_common.service.download import (
    Download, DownloadService)
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.utils import Utils
from urllib.error import HTTPError

# How long a download URL is reused before a new one is asked for. Well inside
# its real lifetime, so a URL that is still in use is never the one about to
# expire; an expired one is caught anyway by the refusal statuses in streaming.
URL_REUSE_SECONDS = 15 * 60

# Per connection to OneDrive, for connect and for each read.
UPSTREAM_TIMEOUT_SECONDS = 20


class DownloadUrls(object):
    """Download URLs shared by the requests of one Kodi session.

    Kodi opens a new request for every seek, so reusing the URL spares a Graph
    round trip each time. When a video starts, Kodi opens several requests for
    it at once (the headers, the index at the end of the file, the start of
    the body); one lock per file makes them share one Graph call instead of
    racing each other through a token check and an item lookup each, which on
    the first video after Kodi starts is the slowest path there is.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._urls = {}
        self._key_locks = {}

    def get(self, key, fetch, fresh=False):
        asked_at = self._clock()
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            with self._lock:
                cached = self._urls.get(key)
            if cached:
                url, fetched_at = cached
                if fresh:
                    # Somebody else replaced it while this request waited
                    # for the lock; that one is as fresh as it gets.
                    if fetched_at > asked_at:
                        return url
                elif self._clock() - fetched_at < URL_REUSE_SECONDS:
                    return url
            url = fetch()
            with self._lock:
                self._urls[key] = (url, self._clock())
            return url


_URLS = DownloadUrls()


def open_upstream(url, method, range_header):
    # Always GET, even when Kodi asked with HEAD: whether the CDN answers HEAD
    # is not something to depend on, and relay() closes the connection after
    # the headers without reading the body.
    headers = {'Range': range_header} if range_header else {}
    request = urllib.request.Request(url, headers=headers, method='GET')
    return urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS)


class StreamingDownload(Download):

    def do_GET(self):
        data = self.path.split('/')
        if len(data) <= 4 or data[1] != self.server.service.name:
            self.write_response(404)
            return
        driveid, item_driveid, item_id = data[2], data[3], data[4]
        provider = self.server.data()
        provider.configure(AccountManager(self.server.service.profile_path),
                           driveid)

        def fetch():
            item = provider.get_item(item_driveid=item_driveid,
                                     item_id=item_id,
                                     include_download_info=True)
            return item['download_info']['url']

        def resolve(fresh):
            return _URLS.get((driveid, item_driveid, item_id), fetch, fresh)

        def send_head(status, headers):
            self.send_response(status)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header('Connection', 'close')
            self.end_headers()

        range_header = self.headers.get('Range')
        label = '%s %s range=%s' % (self.command, item_id, range_header or '-')

        def log(message):
            Logger.notice('stream %s: %s' % (label, message))

        delivered = [0]

        def write(data):
            self.wfile.write(data)
            delivered[0] += len(data)

        try:
            streaming.relay(resolve, open_upstream, self.command, range_header,
                            send_head, write, wait=time.sleep, log=log)
        except (BrokenPipeError, ConnectionResetError) as e:
            if not self.response_code_sent:
                # Nothing reached Kodi: this was OneDrive, not a seek.
                Logger.error('stream %s: %s' % (label, Utils.str(e)))
                self.write_response(502)
                return
            # Kodi closed its end, which is what a seek or a stop looks like --
            # unless OneDrive was the one that broke and could not be resumed,
            # which relay() has already logged.
            Logger.debug('stream %s: ended after %d bytes (%s)'
                         % (label, delivered[0], type(e).__name__))
        except Exception as e:
            if self.response_code_sent:
                # Mid-body; the only thing left is to end the connection.
                Logger.error('stream %s: relay ended after %d bytes: %s'
                             % (label, delivered[0], Utils.str(e)))
                return
            status = 500
            httpex = ExceptionUtils.extract_exception(e, HTTPError)
            if httpex:
                status = httpex.code
            elif isinstance(e, streaming.UpstreamRefused):
                status = 502
            Logger.error(ExceptionUtils.full_stacktrace(e))
            self.write_response(status)


class StreamingDownloadService(DownloadService):

    def __init__(self, provider_class):
        super(StreamingDownloadService, self).__init__(provider_class)
        self._handler = StreamingDownload
