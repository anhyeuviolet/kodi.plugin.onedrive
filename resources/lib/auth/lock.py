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
"""The refresh lock: one token refresh at a time, per account.

The two contenders are the plugin and the background service, and in Kodi they
are sub-interpreters inside ONE operating-system process. That single fact
eliminates both of the mechanisms a reviewer reaches for first, and it does so
silently -- neither raises anything when it fails to exclude:

  * A POSIX record lock is *associated with the process*. The documentation is
    explicit that "a single process can hold only one type of lock on a file
    region; if a new lock is applied to an already-locked region, then the
    existing lock is converted", and that "if a process closes ANY file
    descriptor referring to a file, then all of the process's locks on that file
    are released, regardless of the file descriptor(s) on which the locks were
    obtained". Read against Kodi: the service takes the lock, the plugin -- same
    process -- asks for the same region and is granted it because a process
    cannot conflict with itself, and then the plugin closing its descriptor
    releases the service's lock too. Two failures in one mechanism.

  * A lock object from the standard library's thread module fails one step
    earlier: each sub-interpreter imports its own copy of the module and
    constructs its own object, so one side's is invisible to the other. The tree
    already has such an object in the Kodi utilities module. It is correct for
    what it guards and must stay there; reaching for it here would look like
    serialisation and provide none.

`os.open(path, O_CREAT | O_EXCL)` asks the *filesystem* whether a name already
exists. Nothing about process, thread or interpreter identity enters into it,
which is the whole reason it is the mechanism used here.

Nothing in this module imports a Kodi module. The session identifier and the
wait function are both injected: in production the identifier comes from a home
window property, which every sub-interpreter in one Kodi session can read and
which is cleared when Kodi restarts, and the wait is `Monitor.waitForAbort`,
which is the only correct sleep inside Kodi because it reports a shutdown.
"""

import json
import os
import time
import uuid

# The three answers the staleness test can give. They are three and not two
# because "the modification time is in the future" is genuinely a third thing:
# calling it fresh makes the lock permanent, and calling it stale breaks a
# living holder every time the clock steps.
_FRESH = 'fresh'
_STALE = 'stale'
_UNKNOWN = 'unknown'


class RefreshLock(object):
    """An exclusive-create lock on `lock_path`, with a two-signal stale breaker.

    One instance is one attempt at holding one account's lock. The lock file
    sits beside the token file it protects -- one pair per account -- so two
    accounts never contend; see `store.lock_path`.
    """

    # The lock's lifetime must exceed the worst case of the request it protects,
    # or a live, working refresh gets its lock broken out from under it and the
    # double write this class exists to prevent happens anyway.
    #
    # The arithmetic, and it is not a round number by accident. The transport's
    # own comment computes its worst-case wall time at ITS defaults
    # (tries=4, delay=5, backoff=2, timeout=30) as 4*30 + 5 + 10 + 20 = 155
    # seconds. Plan 03-08 gives the token refresh its own short profile instead
    # -- tries=2, delay=5 -- whose worst case is 2*30 + 5 = 65 seconds. Ninety
    # leaves twenty-five seconds of margin over that.
    #
    # THE DEPENDENCY IS LOAD-BEARING: restoring the transport's default profile
    # for the refresh moves the worst case back to 155 seconds and silently
    # starts breaking live locks. Whoever does that must move this constant too.
    LIFETIME_SECONDS = 90

    # How long to wait between attempts on a lock judged fresh. Passed to the
    # injected wait, which in production is abort-aware.
    POLL_SECONDS = 0.5

    # A ceiling on consecutive breaks within one acquire. Breaking is deliberately
    # not counted against the deadline -- a lock left by a previous Kodi run must
    # cost the caller nothing at all -- so something has to stop a pathological
    # loop against a peer that keeps recreating stale files.
    MAX_BREAKS = 8

    # How far ahead of the reader's clock a modification time may sit before it
    # counts as the clock having stepped. It is not zero because the two values
    # do not come from the same place: the filesystem's timestamp and what
    # time.time() returns are written and read through different paths, and on
    # some hosts a file touched a moment ago reads back a fraction of a second
    # in the future. Without this, a lock touched *right now* is intermittently
    # judged future-dated, and the guard below turns into a second breaker that
    # fires on healthy locks -- which is the exact failure it exists to prevent.
    # A second is far below the lifetime, so it costs the age signal nothing.
    FUTURE_TOLERANCE_SECONDS = 1.0

    def __init__(self, lock_path, session_id, sleep, lifetime=None):
        self._path = os.fspath(lock_path)
        self._session = session_id
        self._sleep = sleep
        self._lifetime = (self.LIFETIME_SECONDS if lifetime is None
                          else lifetime)
        self._fd = None
        self._held = False

    # -- acquiring -------------------------------------------------------

    def acquire(self, timeout):
        """True if this instance now holds the lock, False if it lost the race.

        Losing RETURNS rather than raises, and that is deliberate. It is a
        normal outcome with a defined recovery -- wait, re-read the store, and
        use whatever the winner wrote there -- not an error condition. Raising
        would force every call site to sort "somebody else is refreshing" from
        "the disk is gone", and the two demand opposite responses.
        """
        deadline = time.time() + timeout
        consecutive_unknowns = 0
        breaks = 0

        while True:
            if self._create():
                return True

            verdict = self._staleness()

            if verdict == _UNKNOWN:
                # A modification time in the future means the clock stepped
                # backwards. On a television box with no real-time clock, which
                # sets its clock from the network at boot, that is a normal
                # event rather than an exotic one. It is worth exactly one
                # re-read: a clock that stepped *forward* between the holder's
                # create and this check looks identical, and that holder is
                # alive. Still in the future on the second look and it gets
                # broken -- a permanently-future lock is otherwise unbreakable.
                #
                # CONSECUTIVE, not cumulative. A count that survived an
                # intervening healthy reading would break a live lock on the
                # strength of one stale observation from minutes earlier.
                consecutive_unknowns += 1
                if consecutive_unknowns < 2:
                    if self._sleep(self.POLL_SECONDS):
                        return False
                    continue
                verdict = _STALE
            else:
                consecutive_unknowns = 0

            if verdict == _STALE:
                breaks += 1
                if breaks <= self.MAX_BREAKS and self._break():
                    continue
                # The break itself failed -- on some filesystems a file another
                # holder still has open cannot be renamed. Fall through and wait
                # it out rather than spinning.

            if time.time() >= deadline:
                return False
            if self._sleep(self.POLL_SECONDS):
                return False

    def _create(self):
        """One exclusive create. True if it won, False if the name was taken."""
        try:
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o600)
        except FileExistsError:
            return False

        self._fd = fd
        self._held = True
        # The session identifier and nothing else. This file sits beside a
        # bearer credential, so anything more in it is exposure bought for
        # nothing. No fsync: a lock that does not survive a crash is exactly
        # right, and the session signal below covers the case where one does.
        os.write(fd, json.dumps({'session': self._session}).encode('utf-8'))
        return True

    # -- staleness -------------------------------------------------------

    def _staleness(self):
        """_FRESH, _STALE or _UNKNOWN for the lock file currently on disk.

        Two signals, answering two different questions.

        Question one, "is the holder definitely gone", is answered by the
        session identifier and by nothing else. A lock recorded under a session
        other than the current one was left behind by a previous Kodi run, so it
        is stale on sight, with no waiting at all. That covers the crash and the
        force-stop, which are the common cases on a television box.

        The textbook answer to question one -- record the holder's process id
        and ask the operating system whether it is still running -- is
        DEGENERATE here and must not be used. The holder's process is Kodi's,
        and Kodi is by definition running, because it is the thing asking. Such
        a breaker never breaks anything, including the lock left by a
        sub-interpreter that died mid-refresh, and that is worse than no breaker
        at all, because it is believed.

        Question two, "is the holder stuck", can only be answered by time, and
        only within one session.
        """
        try:
            modified_at = os.stat(self._path).st_mtime
        except OSError:
            # Gone between the failed create and this look: somebody released it
            # or broke it. Retrying the create is exactly the right move.
            return _STALE

        recorded = self._recorded_session()
        if recorded is not None and recorded != self._session:
            return _STALE

        # The file's OWN modification time against the current wall clock. Not a
        # timestamp written into the file and compared against the reader's
        # clock: the modification time puts one clock on both sides of the
        # comparison and removes the question of whose clock is authoritative.
        # A monotonic clock cannot be used at all, because its origin is
        # arbitrary per process and meaningless once written to a file that
        # outlives one.
        age = time.time() - modified_at
        if age < -self.FUTURE_TOLERANCE_SECONDS:
            return _UNKNOWN
        if age >= self._lifetime:
            return _STALE
        return _FRESH

    def _recorded_session(self):
        """The session in the lock file, or None if it cannot be read.

        None is not "no session, therefore stale". A lock file is created and
        then written, so a contender can read it in the gap and see nothing at
        all -- treating that as stale would break a lock a microsecond after it
        was taken. When this returns None the age signal decides alone.
        """
        try:
            with open(self._path, 'r', encoding='utf-8') as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            return None
        if isinstance(record, dict):
            recorded = record.get('session')
            if isinstance(recorded, str) and recorded:
                return recorded
        return None

    def _break(self):
        """Rename the stale lock aside, so that the retry can recreate it.

        Rename-then-recreate rather than unlink-then-create, because it is the
        sequence that stays race-safe when two contenders both judge the same
        lock stale: whoever wins the exclusive create wins, and the loser sees
        the already-exists error and waits. Unlinking and then creating gives
        both of them a create that succeeds.

        A residual double break is survivable and is not worth closing. Two
        contenders CAN both get through here, and the loser's refresh then fails
        with a dead grant, re-reads the store and ADOPTS the token the winner
        wrote (plan 03-08). That backstop is the reason this breaker is allowed
        to be imperfect. Tuning it further trades a rare double refresh for a
        common stall, which is the worse of the two on a device the user cannot
        easily inspect.
        """
        aside = '%s.stale-%s' % (self._path, uuid.uuid4().hex)
        try:
            os.replace(self._path, aside)
        except OSError:
            return False
        try:
            os.unlink(aside)
        except OSError:
            pass
        return True

    # -- holding and letting go ------------------------------------------

    def touch(self):
        """Push the modification time forward, for a holder that expects to
        outlive the lifetime.

        With the short refresh profile of plan 03-08 this should never be
        needed, which is the point of it: the escape hatch exists so that the
        lifetime never has to be raised to cover a slow path.
        """
        try:
            os.utime(self._path, None)
        except OSError:
            pass

    def release(self):
        """Let go. Safe to call twice, and safe to call having never acquired.

        The unlink tolerates an absent file: somebody may have judged this lock
        stale and broken it, and that is a case the design accepts rather than
        an error.
        """
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

        if not self._held:
            # Never held it, or already let go. Unlinking here would remove a
            # lock belonging to somebody else.
            return
        self._held = False

        try:
            os.unlink(self._path)
        except OSError:
            pass
