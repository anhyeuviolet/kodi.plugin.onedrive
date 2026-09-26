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
"""Playback that outlives its download URL.

The reported fault: a video stopped after 20 minutes or an hour and played on
when started again. The loopback service redirected Kodi to a signed URL that
expires, and Kodi kept using it. These drive `resources/lib/streaming.relay`
against a fake OneDrive that expires URLs and drops connections on cue.
"""

import http.client
import io
from urllib.error import HTTPError

import pytest

from resources.lib import streaming

FILE = bytes(range(256)) * 64          # 16 KiB of distinguishable bytes


class _Response(object):
    def __init__(self, status, body, headers, fail_after=None):
        self.status = status
        self.headers = headers
        self._body = io.BytesIO(body)
        self._fail_after = fail_after
        self._read = 0
        self.closed = False
        self.eof_instead = False

    def read(self, n):
        if self._fail_after is not None and self._read >= self._fail_after:
            if self.eof_instead:
                return b''
            raise ConnectionResetError('connection dropped by the far side')
        data = self._body.read(n)
        self._read += len(data)
        return data

    def close(self):
        self.closed = True


class _OneDrive(object):
    """Hands out numbered URLs; only the newest is valid unless told otherwise."""

    def __init__(self, drop_at=()):
        self.issued = 0
        self.expired = set()
        self.requests = []
        self.drops = list(drop_at)

    def resolve(self, fresh):
        if fresh or self.issued == 0:
            self.issued += 1
        return 'https://cdn/%d' % self.issued

    def open(self, url, method, rng):
        self.requests.append((url, method, rng))
        if url in self.expired:
            raise HTTPError(url, 401, 'expired', {}, io.BytesIO())
        wanted = streaming.parse_range(rng)
        if wanted:
            first, last = wanted
            last = len(FILE) - 1 if last is None else last
            body = FILE[first:last + 1]
            status = 206
            headers = {'Content-Length': str(len(body)),
                       'Content-Range': 'bytes %d-%d/%d' % (first, last, len(FILE)),
                       'Content-Type': 'video/x-matroska'}
        else:
            body, status = FILE, 200
            headers = {'Content-Length': str(len(FILE)),
                       'Accept-Ranges': 'bytes',
                       'Content-Type': 'video/x-matroska',
                       'Set-Cookie': 'not for kodi'}
        fail_after = self.drops.pop(0) if self.drops else None
        return _Response(status, body, headers, fail_after)


def _play(onedrive, rng=None, method='GET', **kwargs):
    sent = {}
    out = io.BytesIO()

    def send_head(status, headers):
        sent['status'] = status
        sent['headers'] = dict(headers)

    delivered = streaming.relay(onedrive.resolve, onedrive.open, method, rng,
                                send_head, out.write, chunk_size=1000, **kwargs)
    return sent, out.getvalue(), delivered


def test_the_whole_file_is_relayed_with_only_the_headers_kodi_needs():
    sent, body, delivered = _play(_OneDrive())
    assert body == FILE and delivered == len(FILE)
    assert sent['status'] == 200
    assert sent['headers'] == {'Content-Type': 'video/x-matroska',
                               'Content-Length': str(len(FILE)),
                               'Accept-Ranges': 'bytes'}


def test_an_expired_url_is_replaced_and_the_request_made_again():
    """The reported fault: Kodi asks again long after the URL was issued."""
    onedrive = _OneDrive()
    onedrive.resolve(False)
    onedrive.expired.add('https://cdn/1')

    sent, body, _ = _play(onedrive, rng='bytes=4000-')

    assert sent['status'] == 206
    assert body == FILE[4000:]
    assert [r[0] for r in onedrive.requests] == ['https://cdn/1', 'https://cdn/2']


def test_a_dropped_connection_is_resumed_from_the_next_byte():
    onedrive = _OneDrive(drop_at=[5000])
    sent, body, _ = _play(onedrive)

    assert body == FILE, 'the resumed body must continue exactly where it broke'
    assert onedrive.requests[1][2] == 'bytes=5000-'


def test_a_body_that_ends_early_is_a_drop_not_the_end_of_the_file():
    """http.client reads a connection closed early as an ordinary end."""
    onedrive = _OneDrive(drop_at=[5000])
    original_open = onedrive.open

    def open_quietly(url, method, rng):
        response = original_open(url, method, rng)
        response.eof_instead = True
        return response
    onedrive.open = open_quietly

    _, body, _ = _play(onedrive)
    assert body == FILE
    assert onedrive.requests[1][2] == 'bytes=5000-'


def test_a_drop_after_the_url_expired_resumes_with_a_fresh_url():
    onedrive = _OneDrive(drop_at=[3000])
    original_open = onedrive.open

    def open_and_expire(url, method, rng):
        response = original_open(url, method, rng)
        onedrive.expired.add(url)       # expires while the body is in flight
        return response
    onedrive.open = open_and_expire

    _, body, _ = _play(onedrive, rng='bytes=1000-9999')
    assert body == FILE[1000:10000]
    assert onedrive.requests[-1] == ('https://cdn/2', 'GET', 'bytes=4000-9999')


def test_resuming_gives_up_after_the_limit():
    onedrive = _OneDrive(drop_at=[1000, 0, 0, 0])
    with pytest.raises(ConnectionResetError):
        _play(onedrive, max_reopens=3)
    assert len(onedrive.requests) == 4


def test_a_range_that_cannot_be_located_is_passed_through_but_not_resumed():
    onedrive = _OneDrive(drop_at=[10])
    onedrive_open = onedrive.open

    def suffix(url, method, rng):
        assert rng == 'bytes=-500'
        return _Response(206, FILE[-500:], {'Content-Length': '500'}, 10)
    onedrive.open = suffix
    with pytest.raises(ConnectionResetError):
        _play(onedrive, rng='bytes=-500')
    del onedrive_open


def test_head_sends_headers_and_no_body():
    sent, body, delivered = _play(_OneDrive(), method='HEAD')
    assert sent['status'] == 200 and body == b'' and delivered == 0


def test_a_refusal_that_is_not_expiry_reaches_the_caller_before_any_header():
    onedrive = _OneDrive()

    def missing(url, method, rng):
        raise HTTPError(url, 416, 'range not satisfiable', {}, io.BytesIO())
    onedrive.open = missing
    with pytest.raises(HTTPError) as raised:
        _play(onedrive, rng='bytes=999999-')
    assert raised.value.code == 416


def test_an_unexpected_status_is_refused_rather_than_relayed():
    onedrive = _OneDrive()
    onedrive.open = lambda url, method, rng: _Response(302, b'', {})
    with pytest.raises(streaming.UpstreamRefused):
        _play(onedrive)


def test_kodi_closing_its_end_stops_the_relay():
    onedrive = _OneDrive()

    def gone(data):
        raise BrokenPipeError('kodi seeked')
    with pytest.raises(BrokenPipeError):
        streaming.relay(onedrive.resolve, onedrive.open, 'GET', None,
                        lambda s, h: None, gone)
    assert len(onedrive.requests) == 1, 'a seek must not be retried upstream'


def test_an_incomplete_read_counts_as_a_drop():
    onedrive = _OneDrive()
    first = onedrive.open('https://cdn/1', 'GET', None)
    reads = {'n': 0}

    def flaky(n):
        reads['n'] += 1
        if reads['n'] == 2:
            raise http.client.IncompleteRead(b'')
        return io.BytesIO(FILE).read(n) if reads['n'] == 1 else b''
    first.read = flaky
    calls = []

    def open_url(url, method, rng):
        calls.append(rng)
        if len(calls) == 1:
            return first
        return _OneDrive().open(url, method, rng)

    out = io.BytesIO()
    streaming.relay(lambda fresh: 'https://cdn/1', open_url, 'GET', None,
                    lambda s, h: None, out.write, chunk_size=1000)
    assert calls == [None, 'bytes=1000-']
    assert out.getvalue() == FILE


@pytest.mark.parametrize('header, expected', [
    (None, None), ('', None), ('bytes=0-', (0, None)), ('bytes=10-20', (10, 20)),
    ('bytes=-500', None), ('bytes=0-1,5-9', None), ('bytes=9-1', None),
    ('items=0-1', None)])
def test_range_parsing(header, expected):
    assert streaming.parse_range(header) == expected


def test_download_urls_are_reused_until_they_age(monkeypatch):
    from kodistub import kodi_stubs
    with kodi_stubs('/nonexistent-profile'):
        from resources.lib import stream_service
        now = {'t': 0.0}
        urls = stream_service.DownloadUrls(clock=lambda: now['t'])
        fetched = []

        def fetch():
            fetched.append(1)
            return 'u%d' % len(fetched)

        assert urls.get('k', fetch) == 'u1'
        assert urls.get('k', fetch) == 'u1'
        assert urls.get('k', fetch, fresh=True) == 'u2'
        now['t'] += stream_service.URL_REUSE_SECONDS + 1
        assert urls.get('k', fetch) == 'u3'
