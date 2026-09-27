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
"""Relaying a OneDrive file to Kodi so that playback survives an expired link.

WHY PLAYBACK STOPPED. Kodi plays from the add-on's loopback download service.
That service used to answer with a 307 to the file's pre-authenticated download
URL. Such a URL is signed and short-lived (about an hour), and Kodi remembers
the address it was redirected to: every later request for the same stream --
after a seek, a dropped connection, or a buffer that ran dry -- goes straight to
that address. Once the signature has expired those requests are refused and
playback ends, typically 20 to 60 minutes in. Starting the video again works,
because it asks the service again and gets a fresh URL.

WHAT THIS DOES INSTEAD. The service stays in the path: Kodi only ever talks to
the loopback address, and the service fetches the bytes itself. Three failures
are recovered without Kodi noticing:

  * the download URL is refused as expired (401, 403, 404 or 410): a fresh one
    is asked for and the request is made again, once;
  * OneDrive cannot be reached, or answers 5xx/429, when the stream is opened
    (a cold connection right after Kodi starts is the usual case: name lookup
    and TLS to a CDN host nobody has talked to yet): the open is tried again,
    OPEN_ATTEMPTS times in all, with a short wait between tries;
  * the connection to OneDrive breaks in the middle of the body: the request is
    made again from the first byte not yet delivered, with a Range header. The
    budget is MAX_REOPENS failures *in a row*; any delivered byte resets it, so
    a two-hour film survives any number of isolated drops, and only a far side
    that stays down ends the stream.

Nothing here imports a Kodi module or opens a socket of its own; the opener and
the URL resolver are passed in, so every branch is tested without a network.
"""

import http.client
import re

# The statuses with which a pre-authenticated URL is refused once it is no
# longer valid. Seen in practice: 401 and 403 on business drives, 404 and 410
# on personal ones.
EXPIRED_STATUSES = (401, 403, 404, 410)

# Response headers Kodi needs to seek and to size its buffer. Anything else
# the CDN sends stays on the far side of the relay.
FORWARDED_HEADERS = ('Content-Type', 'Content-Length', 'Content-Range',
                     'Accept-Ranges', 'Last-Modified', 'ETag')

# Statuses worth another try: the far side is busy, not refusing.
RETRY_STATUSES = (429, 500, 502, 503, 504)

CHUNK_SIZE = 64 * 1024
MAX_REOPENS = 5
OPEN_ATTEMPTS = 3

# Seconds to wait before the n-th consecutive retry (the last value repeats).
BACKOFF_SECONDS = (0.5, 1, 2, 4)


def backoff(attempt):
    return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]


_RANGE = re.compile(r'^\s*bytes=(\d+)-(\d*)\s*$')


class UpstreamRefused(Exception):
    """OneDrive answered with a status that cannot be relayed as a stream."""

    def __init__(self, status):
        super(UpstreamRefused, self).__init__('upstream status %s' % status)
        self.status = status


def parse_range(header):
    """(first, last) for a single `bytes=first-[last]` range, else None.

    `last` is None for an open-ended range. A suffix range, several ranges or
    anything malformed is None: it is still passed through as it came, it just
    cannot be resumed, because the first byte is not known.
    """
    if not header:
        return None
    match = _RANGE.match(header)
    if not match:
        return None
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else None
    if last is not None and last < first:
        return None
    return first, last


def resume_range(first, last, delivered):
    return 'bytes=%d-%s' % (first + delivered, '' if last is None else last)


def forwarded_headers(headers):
    """The subset of `headers` (anything with .get) worth giving to Kodi."""
    picked = []
    for name in FORWARDED_HEADERS:
        value = headers.get(name)
        if value:
            picked.append((name, value))
    return picked


def _status(response):
    return getattr(response, 'status', None) or response.getcode()


def _no_wait(seconds):
    return None


def _no_log(message):
    return None


def relay(resolve, open_url, method, range_header, send_head, write,
          max_reopens=MAX_REOPENS, chunk_size=CHUNK_SIZE,
          open_attempts=OPEN_ATTEMPTS, wait=_no_wait, log=_no_log):
    """Fetch the file through `open_url` and hand it to Kodi.

    resolve(fresh)            -> the download URL; fresh=True asks for a new one
    open_url(url, method, rng)-> a response (status, headers, read, close), or
                                 raises urllib.error.HTTPError
    send_head(status, headers)   sends the status line and headers to Kodi
    write(data)                  sends body bytes to Kodi; raises OSError once
                                 Kodi has gone, which is how a seek looks
    wait(seconds)                the pause before a retry
    log(message)                 one line per recovery; never given a URL,
                                 because a download URL is a credential

    Returns the number of body bytes delivered. Raises HTTPError, OSError or
    UpstreamRefused when nothing has been sent yet, so the caller can still
    answer with a status of its own.
    """
    from urllib.error import HTTPError

    def open_once(rng):
        try:
            return open_url(resolve(False), method, rng)
        except HTTPError as error:
            if error.code not in EXPIRED_STATUSES:
                raise
            error.close()
            log('download URL refused (%s), asking for a new one' % error.code)
        return open_url(resolve(True), method, rng)

    def open_retrying(rng, attempts):
        attempt = 0
        while True:
            try:
                return open_once(rng)
            except HTTPError as error:
                if error.code not in RETRY_STATUSES or attempt + 1 >= attempts:
                    raise
                error.close()
                reason = 'status %s' % error.code
            except (OSError, http.client.HTTPException) as error:
                if attempt + 1 >= attempts:
                    raise
                reason = '%s: %s' % (type(error).__name__, error)
            log('open failed (%s), try %d of %d' % (reason, attempt + 2,
                                                   attempts))
            wait(backoff(attempt))
            attempt += 1

    upstream = open_retrying(range_header, max(1, open_attempts))
    status = _status(upstream)
    if status not in (200, 206):
        upstream.close()
        raise UpstreamRefused(status)

    # Where the body starts, so a broken connection can be picked up again.
    # Only when that is known for certain: an answered range, or the whole
    # file from byte zero.
    wanted = parse_range(range_header)
    if status == 206 and wanted:
        first, last = wanted
    elif status == 200 and not range_header:
        first, last = 0, None
    else:
        first = last = None

    # How many body bytes this answer promised. A connection the far side
    # closes early reads as an ordinary end of body from http.client, so the
    # count is the only way to tell a finished file from a broken one.
    try:
        expected = int(upstream.headers.get('Content-Length'))
    except (TypeError, ValueError):
        expected = None

    send_head(status, forwarded_headers(upstream.headers))
    if method == 'HEAD':
        upstream.close()
        return 0

    delivered = 0
    failures = 0
    try:
        while True:
            try:
                data = upstream.read(chunk_size)
                if not data and expected is not None and delivered < expected:
                    raise ConnectionResetError(
                        'body ended after %d of %d bytes' % (delivered, expected))
            except (OSError, http.client.HTTPException) as broken:
                if first is None:
                    raise
                upstream.close()
                upstream = None
                # Reopen until one answers, counting every failure in a row --
                # the drop itself and any reopen that fails too.
                while upstream is None:
                    failures += 1
                    if failures > max_reopens:
                        log('giving up after %d failures in a row at byte %d'
                            % (failures - 1, first + delivered))
                        raise broken
                    log('connection lost at byte %d (%s: %s), reopening, '
                        'try %d of %d' % (first + delivered,
                                          type(broken).__name__, broken,
                                          failures, max_reopens))
                    wait(backoff(failures - 1))
                    try:
                        upstream = open_once(resume_range(first, last,
                                                          delivered))
                    except HTTPError as error:
                        if error.code not in RETRY_STATUSES:
                            raise
                        error.close()
                        broken = error
                    except (OSError, http.client.HTTPException) as error:
                        broken = error
                resumed_status = _status(upstream)
                if resumed_status != 206:
                    # The far side stopped honouring ranges; carrying on would
                    # send Kodi bytes from the wrong offset.
                    raise UpstreamRefused(resumed_status)
                continue
            if not data:
                return delivered
            write(data)
            delivered += len(data)
            failures = 0
    finally:
        if upstream is not None:
            upstream.close()
