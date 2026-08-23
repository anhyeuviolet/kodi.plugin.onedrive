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
"""The token store: read, atomic write, and the merge that must never lose a
rotated refresh token.

Every property here is a filesystem property, so these tests run against a real
directory under tmp_path. A mocked filesystem would assert the code called the
functions it calls, which is not the question -- the question is whether an
interrupted write can destroy a ninety-day credential.
"""

import json
import os
import re
import stat
import time

import pytest

from resources.lib.auth import store


def test_write_then_read_round_trips(store_path):
    blob = {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
        'expires_in': 3655,
        'date': 1755900000.0,
        'issued_at': 1755900000.0,
    }

    store.write(str(store_path), blob)

    assert store.read(str(store_path)) == blob
    assert json.loads(store_path.read_text(encoding='utf-8')) == blob


def test_write_creates_the_file_exclusively_at_mode_0600(monkeypatch,
                                                         store_path):
    """T-03-01. The mode is an argument to the create, not a chmod afterwards:
    a chmod afterwards leaves a window in which the credential exists at a
    wider mode.

    Asserted against the call the code makes rather than against the resulting
    stat, because on Windows -- where this suite is often run -- the mode bits
    do not apply. The device this ships to is Android, where from Android 11 the
    app's own data directory bypasses the storage abstraction layer and the mode
    genuinely does apply. test_written_file_is_not_group_or_world_readable
    covers the enforced case on the platforms that enforce it.
    """
    seen = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, **kwargs):
        seen.append((path, flags, mode))
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, 'open', recording_open)
    store.write(str(store_path), {'access_token': 'a'})

    assert len(seen) == 1, 'the write opened %d descriptors; it should open ' \
                           'exactly one' % len(seen)
    path, flags, mode = seen[0]
    assert mode == 0o600
    assert flags & os.O_CREAT
    assert flags & os.O_EXCL, 'without O_EXCL the write can adopt a file it ' \
                              'did not create'
    assert path != str(store_path), 'the write must go to a temporary file, ' \
                                    'never straight to the target'


@pytest.mark.skipif(os.name == 'nt',
                    reason='Windows does not enforce POSIX mode bits; the '
                           'call itself is asserted in the test above')
def test_written_file_is_not_group_or_world_readable(store_path):
    store.write(str(store_path), {'access_token': 'a'})

    mode = stat.S_IMODE(os.stat(str(store_path)).st_mode)

    # A mask, not an equality: a filesystem is free to report bits this test
    # has no opinion about, and an equality would fail on one of them for a
    # reason that has nothing to do with the credential being exposed.
    assert mode & 0o077 == 0, 'the token file is readable beyond its owner ' \
                              '(mode %o)' % mode


def test_no_temporary_file_survives_a_write(store_dir, store_path):
    store.write(str(store_path), {'access_token': 'a'})

    leftovers = [entry.name for entry in store_dir.iterdir()
                 if entry.name != store_path.name]

    assert not leftovers, 'the write left scratch files behind: %s' % leftovers


def test_the_temporary_file_is_a_sibling_of_the_target(monkeypatch,
                                                       store_path):
    """AUTH-11. rename(2) returns EXDEV across mount points, and on Android the
    system temporary directory is a different mount from the app-private one.
    A temp file anywhere but the target's own directory is a write that fails
    on the device and passes on the developer's laptop."""
    seen = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, **kwargs):
        seen.append(path)
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, 'open', recording_open)
    store.write(str(store_path), {'access_token': 'a'})

    assert os.path.dirname(seen[0]) == os.path.dirname(str(store_path))


def test_reading_an_absent_store_gives_an_empty_blob(store_path):
    """The first sign-in has nothing to merge onto, and that is not an error."""
    assert not store_path.exists()
    assert store.read(str(store_path)) == {}


def test_merge_keeps_the_previous_refresh_token_when_the_response_omits_one():
    """AUTH-12, and the single highest-consequence rule in the phase. A blob
    written without the refresh token is a working add-on that dies ninety days
    later, for every installation at once."""
    previous = {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
        'expires_in': 3655,
    }
    response = {
        'access_token': 'synthetic-access-token-2',
        'expires_in': 4491,
    }

    merged = store.merge_token_response(previous, response)

    assert merged['refresh_token'] == 'synthetic-refresh-token-1'
    assert merged['access_token'] == 'synthetic-access-token-2'
    assert merged['expires_in'] == 4491


def test_merge_sets_date_and_issued_at_from_the_wall_clock():
    merged = store.merge_token_response({}, {'access_token': 'a'}, now=1755900000.0)

    # date is the field oauth2.py already computes expiry from; issued_at is
    # the new one that makes the inactivity clock observable to AUTH-16.
    assert merged['date'] == 1755900000.0
    assert merged['issued_at'] == 1755900000.0


def test_merge_replaces_the_refresh_token_when_the_response_carries_one():
    """The other direction. A rotated refresh token that is not adopted is the
    same outage as a dropped one, arriving a little later."""
    previous = {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
    }
    response = {
        'access_token': 'synthetic-access-token-2',
        'refresh_token': 'synthetic-refresh-token-2',
    }

    merged = store.merge_token_response(previous, response)

    assert merged['refresh_token'] == 'synthetic-refresh-token-2'


def test_an_empty_refresh_token_in_the_response_does_not_erase_the_stored_one():
    """`''` and `None` are omissions, not values. A truthiness test rather than
    a key test is the difference, and getting it wrong empties the credential
    while looking like it wrote one."""
    previous = {'refresh_token': 'synthetic-refresh-token-1'}

    for empty in ('', None):
        merged = store.merge_token_response(
            previous, {'access_token': 'a', 'refresh_token': empty})
        assert merged['refresh_token'] == 'synthetic-refresh-token-1'


def test_merge_onto_nothing_is_the_first_sign_in():
    for previous in ({}, None):
        merged = store.merge_token_response(
            previous, {'access_token': 'a', 'refresh_token': 'r'})
        assert merged['refresh_token'] == 'r'


def test_two_consecutive_writes_each_leave_a_complete_file(store_dir,
                                                           store_path):
    """AUTH-13 in miniature: refresh twice and the file on disk is the second
    token, whole, with nothing of the first left in it and no scratch beside
    it."""
    first = store.merge_token_response({}, {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
        'expires_in': 3655,
    })
    store.write(str(store_path), first)
    assert store.read(str(store_path))['refresh_token'] == \
        'synthetic-refresh-token-1'

    second = store.merge_token_response(store.read(str(store_path)), {
        'access_token': 'synthetic-access-token-2',
        'refresh_token': 'synthetic-refresh-token-2',
        'expires_in': 4491,
    })
    store.write(str(store_path), second)

    on_disk = store.read(str(store_path))
    assert on_disk['refresh_token'] == 'synthetic-refresh-token-2'
    assert on_disk['access_token'] == 'synthetic-access-token-2'
    assert on_disk['expires_in'] == 4491
    assert [entry.name for entry in store_dir.iterdir()] == [store_path.name]


class Unserialisable(object):
    """A value json refuses, so the write fails partway through the dump --
    after the temporary file exists and after some bytes have gone into it."""


def test_an_interrupted_write_leaves_the_previous_file_byte_identical(
        store_dir, store_path):
    """T-03-02, and the property the whole temp-then-replace dance exists for.

    Proven rather than asserted: the previous file's bytes are compared before
    and after a write that dies mid-serialisation.
    """
    good = {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
        'expires_in': 3655,
        'date': 1755900000.0,
        'issued_at': 1755900000.0,
    }
    store.write(str(store_path), good)
    before = store_path.read_bytes()

    doomed = {
        'access_token': 'synthetic-access-token-2',
        'refresh_token': 'synthetic-refresh-token-2',
        'poison': Unserialisable(),
    }
    with pytest.raises(TypeError):
        store.write(str(store_path), doomed)

    assert store_path.read_bytes() == before, \
        'a failed write damaged the previous token file'
    assert store.read(str(store_path)) == good


def test_an_interrupted_write_leaves_no_temporary_file_behind(store_dir,
                                                              store_path):
    store.write(str(store_path), {'access_token': 'a'})

    with pytest.raises(TypeError):
        store.write(str(store_path), {'poison': Unserialisable()})

    leftovers = [entry.name for entry in store_dir.iterdir()
                 if entry.name != store_path.name]
    assert not leftovers, 'a failed write left scratch behind: %s' % leftovers


def test_the_interrupted_write_really_did_create_its_temporary_file(
        monkeypatch, store_path):
    """Otherwise the two tests above would pass on a write that failed before
    it opened anything, and would certify nothing about the crash window."""
    opened = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, **kwargs):
        opened.append(path)
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, 'open', recording_open)
    with pytest.raises(TypeError):
        store.write(str(store_path), {'access_token': 'a',
                                      'poison': Unserialisable()})

    assert len(opened) == 1
    assert not os.path.exists(opened[0])


def _keys_the_vendored_reader_requires():
    """The key names OAuth2._validate_access_tokens actually tests for, read
    out of the vendored source rather than copied into this file.

    Copying them would mean a change to the vendored validator went unnoticed
    here until a device failed on it.
    """
    source = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'resources', 'lib', 'vendor', 'clouddrive_common', 'remote',
        'oauth2.py')
    with open(source, 'r', encoding='utf-8') as handle:
        text = handle.read()

    body = text.split('def _validate_access_tokens')[1].split('\n    def ')[0]
    return set(re.findall(r"'(\w+)' in access_tokens", body))


def test_the_written_blob_satisfies_the_reader_that_already_exists(store_path):
    """The vendored OAuth2 is not being changed, so the blob has to satisfy it
    as it stands: it raises without these keys, and the failure surfaces as a
    request exception long after the write that caused it."""
    required = _keys_the_vendored_reader_requires()
    assert len(required) >= 4, \
        'read %d key names out of _validate_access_tokens; the parse has ' \
        'drifted and this test would pass vacuously' % len(required)

    store.write(str(store_path), store.merge_token_response({}, {
        'access_token': 'synthetic-access-token-1',
        'refresh_token': 'synthetic-refresh-token-1',
        'expires_in': 3655,
    }))
    blob = store.read(str(store_path))

    missing = sorted(key for key in required if key not in blob)
    assert not missing, 'the vendored reader requires %s, which the written ' \
                        'blob does not carry' % missing


def test_a_freshly_written_blob_is_not_already_expired(store_path):
    """oauth2.py refreshes when time.time() > date + expires_in - 600. A blob
    whose date or expires_in went in wrong passes every shape check above and
    still triggers a refresh on the very first request."""
    store.write(str(store_path), store.merge_token_response({}, {
        'access_token': 'a', 'refresh_token': 'r', 'expires_in': 3655,
    }))
    blob = store.read(str(store_path))

    assert time.time() <= blob['date'] + blob['expires_in'] - 600


def test_a_corrupt_store_is_not_silently_read_as_no_account(store_path):
    """Returning {} here would look like a first sign-in, and the next write
    would merge onto nothing and drop a refresh token that was only ever
    unreadable, not gone."""
    store_path.write_text('{"access_token": "a", truncated', encoding='utf-8')

    with pytest.raises(ValueError):
        store.read(str(store_path))
