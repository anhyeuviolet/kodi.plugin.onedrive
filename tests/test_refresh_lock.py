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
"""The refresh lock: the only thing that stops two token refreshes from both
writing.

The property under test is exclusion between two *contenders that share a
process*, because in Kodi the plugin and the background service are
sub-interpreters inside one operating-system process. That is why the two
mechanisms a reader reaches for first are both absent from the module: a POSIX
record lock is associated with the process and is simply granted to the second
asker, and a `threading.Lock` is a per-interpreter object the other side never
sees. Neither raises anything when it fails, so neither can be caught by a test
of the lock alone -- `tests/test_auth_gates.py::test_no_forbidden_lock_primitives`
is what keeps them out, and these tests prove the replacement actually excludes.

Every test here runs against a real file on a real filesystem under `tmp_path`.
An exclusive create is a filesystem property; a mocked one would assert that the
code calls the function it calls, which is not the question.

The two-process case spawns exactly one child and coordinates with it through
files. One spawn, not four: this suite finishes in about two seconds today, and
a lock test that adds a second to that is the first thing anyone stops running.
"""

import json
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from resources.lib.auth.lock import RefreshLock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One Kodi session id. Both the plugin and the service read the same value out
# of the home window, so a contending pair uses the *same* id -- a test that
# gave the two sides different ids would be exercising the previous-session
# path by accident and would prove nothing about exclusion.
SESSION = 'aaaaaaaaaaaa4aaaaaaaaaaaaaaaaaaa'
PREVIOUS_SESSION = 'bbbbbbbbbbbb4bbbbbbbbbbbbbbbbbbb'


def cheap_sleep(seconds):
    """The injected wait.

    In production this is `xbmc.Monitor().waitForAbort`, which returns True when
    Kodi is shutting down; returning False means "no abort, carry on". Here it
    is capped at 10ms so a contended acquire costs the suite nothing.
    """
    time.sleep(min(seconds, 0.01))
    return False


def aborting_sleep(seconds):
    """A wait that reports a shutdown, exactly as waitForAbort does."""
    return True


class RecordingSleep(object):
    """A wait that remembers it was asked, so a test can assert that a lock
    which must break *immediately* did not cost the caller a single interval."""

    def __init__(self, abort=False):
        self.calls = []
        self.abort = abort

    def __call__(self, seconds):
        self.calls.append(seconds)
        time.sleep(min(seconds, 0.01))
        return self.abort


@pytest.fixture
def lock_file(tmp_path):
    """One account's lock file, beside where its token file would be."""
    accounts = tmp_path / 'addon_data' / 'accounts'
    accounts.mkdir(parents=True)
    return accounts / 'synthetic-subject-key.lock'


def plant(path, session=SESSION, age=None, content=None):
    """A lock file as some other holder would have left it.

    `age` is seconds in the past; a negative age puts the modification time in
    the future, which is what a backwards clock step looks like from here.
    """
    if content is None:
        content = json.dumps({'session': session})
    path.write_text(content, encoding='utf-8')
    if age is not None:
        when = time.time() - age
        os.utime(str(path), (when, when))
    return path


def _lock_source():
    with open(os.path.join(REPO_ROOT, 'resources', 'lib', 'auth', 'lock.py'),
              'r', encoding='utf-8') as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# Acquiring, releasing, and the shape of a loss
# ---------------------------------------------------------------------------

def test_a_free_lock_is_acquired_and_released(lock_file):
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)

    assert lock.acquire(1) is True
    assert lock_file.exists()

    lock.release()
    assert not lock_file.exists()


def test_the_lock_file_carries_the_session_and_nothing_else(lock_file):
    """T-03-19. The lock sits beside a bearer credential; there is no reason for
    anything but the session id to be in it, and every reason for nothing else
    to be."""
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)
    try:
        record = json.loads(lock_file.read_text(encoding='utf-8'))
    finally:
        lock.release()

    assert record == {'session': SESSION}


def test_the_lock_is_created_exclusively_at_mode_0600(monkeypatch, lock_file):
    """T-03-19, and the whole mechanism in one assertion: O_EXCL is what makes
    the filesystem -- rather than the process, the thread or the interpreter --
    the thing that decides who won.

    Asserted against the call the code makes rather than a resulting stat,
    because this suite is often run on Windows, which does not enforce POSIX
    mode bits. The device this ships to is Android, where it does.
    """
    seen = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, **kwargs):
        seen.append((path, flags, mode))
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, 'open', recording_open)
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)
    lock.release()

    assert len(seen) == 1, 'acquiring opened %d descriptors; it should open ' \
                           'exactly one' % len(seen)
    path, flags, mode = seen[0]
    assert path == str(lock_file)
    assert mode == 0o600
    assert flags & os.O_CREAT
    assert flags & os.O_EXCL, 'without O_EXCL the create adopts whatever file ' \
                              'is already there, which is the opposite of a lock'


def test_losing_the_race_returns_false_rather_than_raising(lock_file):
    """Losing is a normal outcome with a defined recovery -- wait, re-read the
    store, use what the winner wrote -- so it is a return value. Raising would
    force every call site to decide whether an exception meant "someone else is
    refreshing" or "the disk is gone"."""
    holder = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert holder.acquire(1) is True
    try:
        loser = RefreshLock(str(lock_file), SESSION, cheap_sleep)
        assert loser.acquire(0.05) is False
    finally:
        holder.release()


def test_a_fresh_lock_is_left_alone_by_the_contender(lock_file):
    """The loser must not have broken the holder's lock on its way out."""
    plant(lock_file, session=SESSION, age=1)

    loser = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert loser.acquire(0.05) is False

    assert json.loads(lock_file.read_text(encoding='utf-8')) == \
        {'session': SESSION}


def test_a_shutdown_ends_the_wait_immediately(lock_file):
    """The injected wait is `waitForAbort`, and its True means Kodi is going
    away. A lock loop that ignored it would hold the shutdown open for the whole
    timeout."""
    plant(lock_file, session=SESSION, age=1)
    lock = RefreshLock(str(lock_file), SESSION, aborting_sleep)

    started = time.time()
    assert lock.acquire(30) is False
    assert time.time() - started < 1, \
        'the acquire ignored the abort signal and waited out its timeout'


def test_release_tolerates_a_lock_someone_else_broke(lock_file):
    """A holder whose lock was judged stale and broken is a case the design
    accepts, not an error: the next plan's adopt-the-winner path is what makes
    it survivable. Release must not raise on the way out."""
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)

    breaker = RefreshLock(str(lock_file), PREVIOUS_SESSION, cheap_sleep)
    assert breaker.acquire(1) is True

    lock.release()
    breaker.release()


def test_release_without_an_acquire_is_harmless(lock_file):
    RefreshLock(str(lock_file), SESSION, cheap_sleep).release()


def test_touch_moves_the_modification_time_forward(lock_file):
    """The escape hatch for a holder that expects to outlive the lifetime. With
    the short refresh profile plan 03-08 installs it should never be needed,
    which is the point of it being cheap."""
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)
    try:
        when = time.time() - 3600
        os.utime(str(lock_file), (when, when))
        before = os.stat(str(lock_file)).st_mtime

        lock.touch()

        assert os.stat(str(lock_file)).st_mtime > before
    finally:
        lock.release()


# ---------------------------------------------------------------------------
# Exclusion: two threads, then two processes
# ---------------------------------------------------------------------------

def test_two_threads_in_one_process_never_interleave(lock_file):
    """The in-process half of the property. A `threading.Lock` would pass this
    one and fail the next; an O_EXCL create passes both, which is why the
    module uses the mechanism that is indifferent to who is asking."""
    log = []

    def contend(name, hold):
        lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
        assert lock.acquire(5) is True, '%s never got the lock' % name
        log.append('enter-' + name)
        time.sleep(hold)
        log.append('exit-' + name)
        lock.release()

    first = threading.Thread(target=contend, args=('A', 0.08))
    first.start()

    deadline = time.time() + 5
    while 'enter-A' not in log and time.time() < deadline:
        time.sleep(0.002)
    assert 'enter-A' in log, 'the first thread never entered'

    second = threading.Thread(target=contend, args=('B', 0.0))
    second.start()

    first.join(10)
    second.join(10)

    assert log == ['enter-A', 'exit-A', 'enter-B', 'exit-B'], \
        'the two holds interleaved: %s' % log


CHILD_SOURCE = textwrap.dedent('''
    """Spawned by test_two_processes_serialise. Coordinates through files."""
    import json
    import os
    import sys
    import time

    sys.path.insert(0, sys.argv[1])
    from resources.lib.auth.lock import RefreshLock

    lock_path, blocked_flag, release_flag, result_path, session = sys.argv[2:7]


    def sleep(seconds):
        time.sleep(min(seconds, 0.01))
        return False


    result = {}
    lock = RefreshLock(lock_path, session, sleep)

    # The parent holds it right now. This must fail, and must fail by
    # returning rather than by raising.
    result['refused_while_the_parent_held_it'] = lock.acquire(0.05) is False
    open(blocked_flag, 'w').close()

    deadline = time.time() + 20
    while not os.path.exists(release_flag) and time.time() < deadline:
        time.sleep(0.005)

    result['acquired_after_the_parent_released'] = lock.acquire(5) is True
    result['the_file_exists_while_held'] = os.path.exists(lock_path)
    lock.release()
    result['the_file_is_gone_after_release'] = not os.path.exists(lock_path)

    with open(result_path, 'w') as handle:
        json.dump(result, handle)
''')


def test_two_processes_serialise(tmp_path, lock_file):
    """The half a `threading.Lock` cannot do, and the half an `fcntl.lockf`
    would appear to do while doing the opposite.

    One spawn, coordinated through files: the child reports that it was refused
    while the parent held the lock, and that it got the lock once the parent let
    go. Both halves matter -- a lock that always refuses would pass the first
    assertion on its own.
    """
    script = tmp_path / 'contender.py'
    script.write_text(CHILD_SOURCE, encoding='utf-8')
    blocked_flag = tmp_path / 'child-was-refused'
    release_flag = tmp_path / 'parent-has-released'
    result_path = tmp_path / 'child-result.json'

    parent = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert parent.acquire(1) is True

    child = subprocess.Popen([
        sys.executable, str(script), REPO_ROOT, str(lock_file),
        str(blocked_flag), str(release_flag), str(result_path), SESSION,
    ])
    try:
        deadline = time.time() + 30
        while not blocked_flag.exists() and time.time() < deadline:
            if child.poll() is not None:
                break
            time.sleep(0.01)
        assert blocked_flag.exists(), \
            'the child never reported back; it exited %r' % child.poll()

        parent.release()
        release_flag.write_text('go', encoding='utf-8')

        assert child.wait(30) == 0, 'the child process failed'
    finally:
        if child.poll() is None:
            child.kill()

    result = json.loads(result_path.read_text(encoding='utf-8'))
    assert result == {
        'refused_while_the_parent_held_it': True,
        'acquired_after_the_parent_released': True,
        'the_file_exists_while_held': True,
        'the_file_is_gone_after_release': True,
    }


# ---------------------------------------------------------------------------
# Staleness signal 1: "the holder is definitely gone"
# ---------------------------------------------------------------------------

def test_a_lock_from_a_previous_session_is_stale_immediately(lock_file):
    """The crash and force-stop cases, which are the common ones on a
    television box. The home-window property that carries the session id is
    cleared when Kodi restarts, so a differing id means the holder cannot
    possibly still be running -- and there is nothing to wait for."""
    plant(lock_file, session=PREVIOUS_SESSION, age=0)
    sleep = RecordingSleep()

    lock = RefreshLock(str(lock_file), SESSION, sleep)

    assert lock.acquire(30) is True
    assert sleep.calls == [], \
        'a lock left by a previous Kodi run cost the caller %d wait(s); it is ' \
        'stale on sight' % len(sleep.calls)
    assert json.loads(lock_file.read_text(encoding='utf-8')) == \
        {'session': SESSION}
    lock.release()


def test_a_previous_session_lock_is_broken_however_recently_it_was_touched(
        lock_file):
    """Signal 1 does not consult the clock at all. A box that crashed one second
    ago leaves a lock whose age is zero; waiting out a lifetime for it would
    wedge the add-on for a minute after every crash."""
    plant(lock_file, session=PREVIOUS_SESSION)
    os.utime(str(lock_file), None)

    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert lock.acquire(1) is True
    lock.release()


def test_the_breaker_never_asks_whether_a_process_is_alive():
    """AUTH-14's prohibition, asserted against the source.

    The textbook breaker reads a pid out of the lock file and calls
    `os.kill(pid, 0)`. Under Kodi that question is degenerate: the holder's
    process is Kodi's, and Kodi is by definition running, because it is the
    thing asking. A breaker built on it never breaks anything -- including the
    lock left by a sub-interpreter that died mid-refresh -- and is worse than no
    breaker at all, because it is believed.
    """
    source = _lock_source()
    for forbidden in ('os.kill', 'psutil', "'pid'", '"pid"'):
        assert forbidden not in source, \
            'the stale-lock breaker reaches for %s; process liveness cannot ' \
            'answer this question in Kodi' % forbidden


# ---------------------------------------------------------------------------
# Staleness signal 2: "the holder is stuck"
# ---------------------------------------------------------------------------

def test_a_lock_older_than_the_lifetime_is_broken(lock_file):
    plant(lock_file, session=SESSION, age=RefreshLock.LIFETIME_SECONDS + 5)

    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)

    assert lock.acquire(1) is True
    assert json.loads(lock_file.read_text(encoding='utf-8')) == \
        {'session': SESSION}
    lock.release()


def test_a_lock_younger_than_the_lifetime_is_not_broken(lock_file):
    """The failure this guards is the expensive one: breaking the lock of a
    live, working refresh produces the double write the lock exists to
    prevent."""
    plant(lock_file, session=SESSION, age=RefreshLock.LIFETIME_SECONDS - 5)

    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)

    assert lock.acquire(0.05) is False


def test_a_touched_lock_stays_fresh_past_its_lifetime(lock_file):
    plant(lock_file, session=SESSION, age=RefreshLock.LIFETIME_SECONDS + 5)
    os.utime(str(lock_file), None)

    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)

    assert lock.acquire(0.05) is False


def test_a_future_dated_lock_is_not_treated_as_fresh(lock_file):
    """A box with no real-time clock sets its clock at boot, so a backwards step
    is a normal event here rather than an exotic one. A modification time in the
    future must not read as "very recently touched", because that lock would be
    unbreakable forever."""
    plant(lock_file, session=SESSION, age=-3600)
    sleep = RecordingSleep()

    lock = RefreshLock(str(lock_file), SESSION, sleep)

    assert lock.acquire(30) is True, \
        'a future-dated lock was treated as fresh and became permanent'
    assert sleep.calls, \
        'a future modification time is "unknown", not "stale": it is worth one ' \
        're-read before breaking, because an NTP step between create and check ' \
        'is exactly what it looks like'
    lock.release()


def test_a_future_dated_lock_that_becomes_sane_is_left_alone(lock_file):
    """The re-read is what makes the guard a guard rather than a second breaker:
    a clock that steps *forward* between the holder's create and this check puts
    the mtime briefly in the future, and that holder is alive."""
    plant(lock_file, session=SESSION, age=-3600)

    def fix_the_clock_then_report_no_abort(seconds):
        os.utime(str(lock_file), None)
        return False

    lock = RefreshLock(str(lock_file), SESSION,
                       fix_the_clock_then_report_no_abort)

    assert lock.acquire(0.05) is False


def test_an_unparseable_lock_file_falls_back_to_the_age_signal(lock_file):
    """A lock file is created and then written, so a contender can read it in
    between and see nothing. That must not read as "no session, therefore
    stale" -- it would break a lock a microsecond after it was taken.
    """
    plant(lock_file, content='', age=0)
    fresh = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert fresh.acquire(0.05) is False, \
        'a lock file caught mid-creation was broken by its contender'

    plant(lock_file, content='', age=RefreshLock.LIFETIME_SECONDS + 5)
    aged = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    assert aged.acquire(1) is True, \
        'an unreadable lock file with no session and an old mtime is stale by ' \
        'age and must still be breakable'
    aged.release()


# ---------------------------------------------------------------------------
# Breaking, and the arithmetic behind the lifetime
# ---------------------------------------------------------------------------

def test_breaking_leaves_no_scratch_behind(lock_file):
    """The break renames the stale file aside before recreating, so that whoever
    wins the recreate wins and the loser sees the already-exists error. The
    renamed-aside file is rubbish the moment the rename returns."""
    directory = lock_file.parent
    plant(lock_file, session=PREVIOUS_SESSION)

    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)

    assert [entry.name for entry in directory.iterdir()] == [lock_file.name]
    lock.release()
    assert [entry.name for entry in directory.iterdir()] == []


def test_the_break_recreates_rather_than_adopting(monkeypatch, lock_file):
    """Adopting the stale file -- opening it without O_EXCL, or unlinking and
    then opening -- loses the race that the rename-then-recreate sequence wins.
    Both contenders would 'succeed' and both would refresh."""
    plant(lock_file, session=PREVIOUS_SESSION)
    seen = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, **kwargs):
        seen.append(flags)
        return real_open(path, flags, mode, **kwargs)

    monkeypatch.setattr(os, 'open', recording_open)
    lock = RefreshLock(str(lock_file), SESSION, cheap_sleep)
    lock.acquire(1)
    lock.release()

    assert seen, 'the acquire opened nothing at all'
    assert all(flags & os.O_EXCL for flags in seen), \
        'the break adopted the stale file instead of recreating it'


def test_the_lifetime_exceeds_the_refresh_worst_case_and_says_why():
    """The constant is set against a measured worst case, not a round number,
    and the number it is set against is a consequence of the request profile the
    refresh uses. Anybody restoring the transport's default profile moves the
    worst case to 155 seconds and silently starts breaking live locks, so the
    arithmetic and its owning plan are named in the source and asserted here.
    """
    source = _lock_source()

    assert RefreshLock.LIFETIME_SECONDS >= 60, \
        'a lifetime below a minute cannot cover a refresh with any retry at all'
    assert '155' in source, \
        "the transport's own worst-case computation is the number this " \
        'constant is set against; it belongs beside it'
    assert '03-08' in source, \
        'the short retry profile this lifetime depends on is installed by plan ' \
        '03-08 and must be named, or it will be undone by somebody who does ' \
        'not know this constant exists'


def test_the_module_records_that_an_imperfect_breaker_is_deliberate():
    """This is the reasoning most likely to be 'hardened' into a worse design by
    a later reader: two contenders can both judge a lock stale, and the residual
    double break is absorbed by the adopt-the-winner path. Tuning the breaker to
    close it trades a rare double refresh for a common stall."""
    source = _lock_source()
    assert 'adopt' in source.lower(), \
        'the backstop that makes an imperfect breaker survivable is not named ' \
        'in the source'
