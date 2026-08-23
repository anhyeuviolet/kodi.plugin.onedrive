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
"""Everything `resources/lib/auth/` needs from Kodi, and nothing else.

That package deliberately contains no Kodi: the protocol, the token store and
the cross-process lock are all testable without a stub library because every
Kodi-shaped thing they need arrives as an argument. This module is the other
half of that arrangement -- the one place those arguments are produced.

Four things, and the list is closed on purpose. A fifth would mean the pure
package had grown a dependency on Kodi that nobody noticed:

  * `profile_path()`  -- `special://profile/addon_data/<id>` resolved to an
                         ordinary OS path, because `store` takes a real path and
                         has never heard of a Kodi virtual filesystem.
  * `session_id()`    -- the identifier `RefreshLock` compares against to tell
                         "the holder is another sub-interpreter of this Kodi
                         session" from "the holder is a process that died before
                         Kodi restarted".
  * `wait(seconds)`   -- the only sleep any of this is allowed to perform. It
                         returns True when Kodi is shutting down, which is what
                         makes a fifteen-minute poll loop interruptible within a
                         second.
  * `log(message)`    -- one line to the Kodi log.
"""

import os
import uuid

import xbmc

from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils

# The window property that carries the session identifier. A home-window
# property is shared by every sub-interpreter in one Kodi session -- the service
# and each plugin invocation are separate interpreters in one process -- and it
# is gone when Kodi restarts. That is exactly the signal the lock needs: a lock
# file naming a session other than this one was written before this Kodi
# started, and its holder cannot still be running.
#
# Suffixed onto the add-on's own id rather than written as a literal, so a rename
# cannot leave two add-ons sharing one property.
SESSION_PROPERTY_SUFFIX = '.auth.session'

# One monitor for the lifetime of the interpreter. Constructing one per wait
# would work, but a poll loop ticking once a second for a quarter of an hour
# would construct nine hundred of them.
_monitor = None


def _session_property():
    return KodiUtils.get_addon_info('id') + SESSION_PROPERTY_SUFFIX


def profile_path(create=True):
    """The add-on's data directory as an ordinary OS path.

    `store` and `lock` both take real paths: they need `O_EXCL`, `fsync`, mode
    bits and `os.replace`, and `xbmcvfs` offers none of the four. Translating
    once, here, is what keeps the translation out of the pure package.

    `create` defaults to True because a brand-new add-on id means a brand-new
    `addon_data` directory: on a first sign-in it does not exist yet, and the
    first thing that happens is a write into it.
    """
    path = KodiUtils.translate_path(KodiUtils.get_addon_info('profile'))
    # translatePath returns str on every Kodi this add-on supports, but the
    # value has been bytes on older builds and os.path is unforgiving about the
    # mix. One coercion here is cheaper than the failure it prevents.
    if isinstance(path, (bytes, bytearray)):
        path = path.decode('utf-8')
    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            # Failing here would be indistinguishable from the caller's own
            # write failing, and the caller's failure carries the better
            # message. Let it be the one that speaks.
            pass
    return path


def session_id():
    """This Kodi session's identifier, generated on first ask.

    Read before write, so every sub-interpreter in one session agrees. Generated
    here rather than by the service, because a plugin-only invocation -- the
    user opening the add-on with the service not yet up -- still has to have a
    session to compare a lock file against, and one generated per interpreter
    would make every sub-interpreter look like a different session to every
    other one.
    """
    key = _session_property()
    value = KodiUtils.get_home_property(key)
    if not value:
        value = uuid.uuid4().hex
        KodiUtils.set_home_property(key, value)
    return value


def wait(seconds):
    """Sleep for `seconds`; return True if Kodi wants to shut down.

    `Monitor.waitForAbort` and nothing else. `time.sleep` and `xbmc.sleep` both
    ignore the abort flag, and a sign-in loop that can run for a quarter of an
    hour must not be the reason a shutdown hangs.
    """
    global _monitor
    if _monitor is None:
        _monitor = xbmc.Monitor()
    return _monitor.waitForAbort(seconds)


def aborted():
    """True if Kodi is shutting down, without waiting at all."""
    return wait(0)


def log(message):
    """One debug line. Callers never put a whole credential in one."""
    Logger.debug(message)
