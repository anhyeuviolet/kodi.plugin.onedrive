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
"""One account's token blob: read it, merge a token response onto it, and
write it back without ever being able to lose it.

`path` here is an ordinary OS path. The caller resolves
`special://profile/addon_data/...` with `xbmcvfs.translatePath` once and passes
the result in; nothing below imports a Kodi module, which is what lets AUTH-13
be tested at all.

`xbmcvfs` could not do this job in any case: it exposes `rename` but no
`replace`, no way to pass `O_EXCL`, no `fsync`, and no mode bits. `os` has all
four and is documented to raise rather than return a bool.
"""

import json
import os
import time
import uuid


def read(path):
    """The stored blob, or {} if nothing has been stored yet.

    An absent file is the ordinary state before the first sign-in and is not an
    error. A file that exists but will not parse *is* an error and is raised:
    the alternative -- treating corruption as "no account" -- silently discards
    a ninety-day refresh token and re-prompts the user, which is precisely the
    outcome the rest of this module exists to prevent.
    """
    path = os.fspath(path)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def write(path, payload):
    """Replace `path` with `payload` as JSON, atomically.

    A reader either sees the whole previous blob or the whole new one, never a
    truncated file and never an empty one. Four details carry that guarantee and
    each is load-bearing:
    """
    path = os.fspath(path)

    # 1. The temporary file is a sibling of the target. rename(2) returns EXDEV
    #    when the two paths are on different mounted filesystems, and on Android
    #    the app-private directory is a different mount from anything
    #    tempfile.gettempdir() would hand back -- so a system temp directory
    #    gives a write that passes on a laptop and fails on the device.
    # 2. The name is unique. Two writers colliding on a fixed '.tmp' name would
    #    make the second fail on O_EXCL rather than proceed, and the failure
    #    would be indistinguishable from a real one.
    tmp = '%s.tmp-%s' % (path, uuid.uuid4().hex)

    # 4. The mode is an argument to the create, not a chmod afterwards. A chmod
    #    afterwards leaves a window, however short, in which a bearer credential
    #    exists at a wider mode. os.replace renames the inode, so the mode set
    #    here is the mode the final file has.
    handle = os.fdopen(
        os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w',
        encoding='utf-8')
    try:
        try:
            json.dump(payload, handle)
            handle.flush()
            # 3. The sync precedes the replace. Without it the rename can land
            #    before the data does, and a power cut leaves a correctly-named
            #    empty credential file -- worse than no file, because it parses.
            #    (Syncing the directory afterwards would make the rename itself
            #    durable too; that is beyond what AUTH-11 asks and is skipped.)
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(tmp, path)
    except BaseException:
        # The target has not been touched at this point, so removing the
        # temporary file restores the state exactly as it was.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def merge_token_response(previous, response, now=None):
    """The previous blob with `response` laid over it.

    A refresh response that omits `refresh_token` means keep the previous one.
    Never the reverse, and never a blob assembled from the response alone. This
    is the highest-consequence rule in the phase and the only one whose breakage
    is invisible for ninety days: a token file written without a refresh token
    is a working add-on that stops working, for every installation at once, on
    the day the last access token ages out (AUTH-12).

    `expires_in` is whatever the response said. The spike measured 3655, 4491
    and 3599 seconds across three runs -- Entra randomises it deliberately -- so
    a constant would be wrong by measurement, not by taste.

    `now` exists so a test can pin the clock; production passes nothing.
    """
    merged = dict(previous or {})
    merged.update(response)

    if not response.get('refresh_token'):
        carried = (previous or {}).get('refresh_token')
        if carried:
            merged['refresh_token'] = carried

    if now is None:
        now = time.time()
    # `date` is the field the existing OAuth2 reader computes expiry from
    # (date + expires_in - 600); it is not new and must keep that name.
    merged['date'] = now
    # `issued_at` is new. It makes the inactivity clock observable, which is
    # what the proactive startup refresh needs to decide whether the ninety-day
    # window is at risk (AUTH-16).
    merged['issued_at'] = now
    return merged
