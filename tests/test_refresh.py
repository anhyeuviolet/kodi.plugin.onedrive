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
"""The refresh path, and the one proof this phase cannot ship without.

`test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens` is that
proof. The provider replaces the refresh token on every use and does not revoke
the old one, so code that keeps re-sending the original works perfectly in
development, works perfectly through a two-week test cycle, and then fails for
every installation on the same day, ninety days after sign-in, with no code
change to blame. Nothing else in this file is as important, and every assertion
in it is made against **what is on disk** rather than against a returned value:
a test that asserted a return value would pass against code that never wrote.

The second half of the file is the race. Two contenders, one token, and a
provider that answers `invalid_grant` to whichever of them arrives second --
which is indistinguishable, from the response alone, from a genuinely dead
grant. The store is re-read from disk and the stored token compared byte-for-
byte against the one just rejected; that comparison is the whole difference
between a harmless wait and signing a user out of a working account.

Nothing here imports a Kodi module and nothing here opens a socket. The HTTP
port is the same injected callable the rest of the package takes,
`post(url, fields) -> (status, body)`, and the wait is the same injected sleep.
"""

import json
import os
import subprocess
import sys
import textwrap
import threading
import time

import pytest

from resources.lib.auth import (device_code, errors, refresh as refresh_module,
                                store)
from resources.lib.auth.lock import RefreshLock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One Kodi session id for every contender, because the plugin and the service
# read the same value out of the home window. Two different ids would exercise
# the previous-session staleness path by accident.
SESSION = 'aaaaaaaaaaaa4aaaaaaaaaaaaaaaaaaa'

# The subject claim out of an identity token, which is what keys an account's
# files on disk.
ACCOUNT = 'AAAAAAAAAAAAAAAAAAAAAJ1zzz-first_account'

# Short enough that a test whose point is that an acquire is *refused* does not
# spend the lock's real timeout doing it. Every such test pays this in full, so
# the number is the suite's budget rather than a detail.
REFUSED_TIMEOUT = 0.05


def no_wait(seconds):
    """The injected sleep, in the shape production uses: returns True on abort.

    A cap rather than a plain return, because a caller that polls in a tight
    loop against a real deadline would otherwise spin the CPU for the whole
    timeout instead of merely waiting it out.
    """
    time.sleep(min(seconds, 0.01))
    return False


def aborting_wait(seconds):
    """The shutdown case. `Monitor.waitForAbort` returns True when Kodi is
    going away, and every wait in this package has to honour that."""
    return True


@pytest.fixture
def profile(tmp_path):
    """The resolved profile directory, already translated by the Kodi layer."""
    path = tmp_path / 'addon_data'
    path.mkdir()
    store.accounts_dir(str(path), create=True)
    return str(path)


@pytest.fixture
def token_file(profile):
    return store.token_path(profile, ACCOUNT)


@pytest.fixture
def lock_file(profile):
    return store.lock_path(profile, ACCOUNT)


@pytest.fixture
def signed_in(token_file):
    """A blob in the state a completed sign-in leaves behind."""
    blob = {
        'token_type': 'Bearer',
        'scope': 'https://graph.microsoft.com/Files.Read openid profile',
        'expires_in': 3655,
        'access_token': 'access-token-0',
        'refresh_token': 'refresh-token-0',
        'date': 1000.0,
        'issued_at': 1000.0,
    }
    store.write(token_file, blob)
    return blob


def new_lock(lock_file, sleep=no_wait):
    return RefreshLock(str(lock_file), SESSION, sleep)


class RecordingPost(object):
    """The HTTP port, scripted, with the calls kept.

    Running off the end of the script fails loudly rather than repeating the
    last answer: a refresh that exchanges one more time than the test intended
    is exactly the bug this file exists to catch.
    """

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []

    def __call__(self, url, fields):
        self.calls.append((url, dict(fields)))
        if not self.queue:
            raise AssertionError(
                'the token endpoint was called %d time(s) but only %d '
                'response(s) were scripted' % (len(self.calls),
                                               len(self.calls) - 1))
        return self.queue.pop(0)

    @property
    def exchanges(self):
        return len(self.calls)

    @property
    def refresh_tokens_sent(self):
        return [fields.get('refresh_token') for _url, fields in self.calls]


def rotated(index, **overrides):
    """A successful refresh response carrying its own new refresh token.

    `expires_in` is one of the three values the spike measured rather than the
    round number, so a test that assumed 3600 fails.
    """
    answer = {
        'token_type': 'Bearer',
        'scope': 'https://graph.microsoft.com/Files.Read openid profile',
        'expires_in': 4491,
        'access_token': 'access-token-%d' % index,
        'refresh_token': 'refresh-token-%d' % index,
    }
    answer.update(overrides)
    return 200, answer


def stored(token_file):
    return store.read(token_file)


# ---------------------------------------------------------------------------
# The proof (AUTH-13)
# ---------------------------------------------------------------------------

def test_two_consecutive_refreshes_leave_three_distinct_refresh_tokens(
        profile, token_file, lock_file, signed_in):
    """The one non-negotiable automated proof in this phase.

    Microsoft's own wording: "Refresh tokens replace themselves with a fresh
    token upon every use. The Microsoft identity platform doesn't revoke old
    refresh tokens when used to fetch new access tokens." Code that persists the
    access token and keeps re-sending the ORIGINAL refresh token therefore
    passes every functional test anybody writes, until the original hits its
    ninety-day lifetime.

    Three values in sequence, all different, and the last of them the one on
    disk. Asserted against the file, not against a return value.
    """
    observed = [stored(token_file)['refresh_token']]

    for index in (1, 2):
        post = RecordingPost(rotated(index))
        result = refresh_module.refresh(profile, ACCOUNT,
                                        new_lock(lock_file), post, no_wait)
        assert result.outcome == refresh_module.SUCCEEDED
        observed.append(stored(token_file)['refresh_token'])

    assert len(set(observed)) == 3, \
        'the persisted refresh token did not change across two refreshes: %s' \
        % (observed,)
    assert stored(token_file)['refresh_token'] == observed[-1]
    assert stored(token_file)['access_token'] == 'access-token-2'


def test_each_exchange_sends_the_token_the_previous_one_returned(
        profile, token_file, lock_file, signed_in):
    """The other half of rotation: the new token has to be *used*, not merely
    stored. Storing it and then sending the original is the same failure with
    an extra step."""
    sent = []
    for index in (1, 2):
        post = RecordingPost(rotated(index))
        refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file), post,
                               no_wait)
        sent.extend(post.refresh_tokens_sent)

    assert sent == ['refresh-token-0', 'refresh-token-1']


def test_a_response_without_a_refresh_token_keeps_the_stored_one(
        profile, token_file, lock_file, signed_in):
    """Never the reverse. A blob written from the response alone is a working
    add-on that stops working for everybody at once (AUTH-12)."""
    body = dict(rotated(1)[1])
    del body['refresh_token']
    post = RecordingPost((200, body))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.SUCCEEDED
    assert stored(token_file)['refresh_token'] == 'refresh-token-0'


def test_a_response_without_a_refresh_token_still_advances_the_access_token(
        profile, token_file, lock_file, signed_in):
    """Keeping the previous refresh token must not mean keeping the previous
    everything: the access token and the issue time still move, or the
    inactivity clock the startup check reads never advances."""
    body = dict(rotated(1)[1])
    del body['refresh_token']
    post = RecordingPost((200, body))

    refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file), post,
                           no_wait, now=5000.0)

    blob = stored(token_file)
    assert blob['access_token'] == 'access-token-1'
    assert blob['issued_at'] == 5000.0
    assert blob['date'] == 5000.0


# ---------------------------------------------------------------------------
# The cheap path: a contender that loses the lock adopts rather than exchanges
# ---------------------------------------------------------------------------

def test_a_contender_that_cannot_acquire_adopts_the_winners_token(
        profile, token_file, lock_file, signed_in):
    """The common case, and it must cost no network call at all.

    The winner holds the lock and has already written. The loser waits,
    re-reads FROM DISK, sees an access token that is not the one it started
    with, and returns it.
    """
    winner = new_lock(lock_file)
    assert winner.acquire(1) is True
    post = RecordingPost()              # any call at all fails the test

    def wait_during_which_the_winner_writes(seconds):
        # The winner finishes while this contender is inside its wait, which is
        # what waiting for a refresh already in flight actually looks like.
        # Doing it before the call instead would mean this contender never held
        # the old token, and the test would prove nothing about re-reading.
        store.write(token_file, dict(signed_in, access_token='access-token-9',
                                     refresh_token='refresh-token-9'))
        return False

    try:
        result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                        post,
                                        wait_during_which_the_winner_writes,
                                        acquire_timeout=REFUSED_TIMEOUT)
    finally:
        winner.release()

    assert result.outcome == refresh_module.SUCCEEDED
    assert result.adopted is True
    assert result.exchanged is False
    assert post.exchanges == 0
    assert result.blob['refresh_token'] == 'refresh-token-9'


def test_a_contender_that_gets_the_lock_after_the_winner_wrote_does_not_exchange(
        profile, token_file, lock_file, signed_in):
    """The same adoption, one step later. Having waited for the lock and got
    it, the blob must be re-read UNDER the lock: whatever was loaded before the
    acquire is a snapshot from before the winner wrote."""
    post = RecordingPost()

    class WriteThenYield(object):
        """A lock whose acquire succeeds, but only after the winner's write has
        landed -- which is exactly what waiting for a real one looks like."""

        def acquire(self, timeout):
            store.write(token_file, dict(signed_in,
                                         access_token='access-token-9',
                                         refresh_token='refresh-token-9'))
            return True

        def release(self):
            pass

    result = refresh_module.refresh(profile, ACCOUNT, WriteThenYield(), post,
                                    no_wait)

    assert result.outcome == refresh_module.SUCCEEDED
    assert result.adopted is True
    assert post.exchanges == 0
    assert stored(token_file)['refresh_token'] == 'refresh-token-9'


def test_a_loser_that_sees_no_change_gives_up_after_a_bounded_number_of_tries(
        profile, token_file, lock_file, signed_in):
    """Bounded, not indefinite. A holder that never finishes must cost the
    other side a defined wait and then a transient answer -- not a stall, and
    above all not a sign-out."""
    holder = new_lock(lock_file)
    assert holder.acquire(1) is True
    try:
        waits = []

        def counting_wait(seconds):
            waits.append(seconds)
            return False

        post = RecordingPost()
        result = refresh_module.refresh(profile, ACCOUNT,
                                        new_lock(lock_file, counting_wait),
                                        post, counting_wait,
                                        acquire_timeout=REFUSED_TIMEOUT)
    finally:
        holder.release()

    assert result.outcome == refresh_module.TRANSIENT
    assert result.adopted is False
    assert post.exchanges == 0
    assert waits, 'the loser never waited at all'
    assert stored(token_file)['refresh_token'] == 'refresh-token-0', \
        'a contender that never got in changed the store'


def test_a_shutdown_during_the_adopt_wait_ends_the_call_at_once(
        profile, token_file, lock_file, signed_in):
    """`Monitor.waitForAbort` returning True means Kodi is going away. A
    refresh that ignored it would hold the shutdown open for its whole
    bounded wait."""
    holder = new_lock(lock_file)
    assert holder.acquire(1) is True
    try:
        post = RecordingPost()
        result = refresh_module.refresh(profile, ACCOUNT,
                                        new_lock(lock_file, aborting_wait),
                                        post, aborting_wait,
                                        acquire_timeout=REFUSED_TIMEOUT)
    finally:
        holder.release()

    assert result.outcome == refresh_module.TRANSIENT
    assert post.exchanges == 0


def test_a_blob_with_no_refresh_token_needs_reauthorisation_without_a_call(
        profile, token_file, lock_file):
    """There is no grant to refresh. Going to the network to be told so costs a
    round trip and answers nothing."""
    store.write(token_file, {'access_token': 'access-token-0'})
    post = RecordingPost()

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.NEEDS_REAUTHORISATION
    assert post.exchanges == 0


# ---------------------------------------------------------------------------
# The lock is held across the exchange and let go whatever happens
# ---------------------------------------------------------------------------

def test_the_exchange_happens_between_an_acquire_and_a_release(
        profile, token_file, lock_file, signed_in):
    """Serialisation is the point of the lock; an exchange outside it is a
    refresh the other contender cannot see coming."""
    log = []

    class RecordingLock(object):
        def acquire(self, timeout):
            log.append('acquire')
            return True

        def release(self):
            log.append('release')

    def post(url, fields):
        log.append('exchange')
        return rotated(1)

    refresh_module.refresh(profile, ACCOUNT, RecordingLock(), post, no_wait)

    assert log == ['acquire', 'exchange', 'release']


def test_the_lock_is_released_when_the_exchange_raises(
        profile, token_file, lock_file, signed_in):
    """A raised exchange that left the lock held would block the other
    contender for a whole lifetime -- ninety seconds in which the add-on looks
    wedged for a reason nobody can see."""
    def exploding_post(url, fields):
        raise RuntimeError('the port blew up')

    lock = new_lock(lock_file)
    result = refresh_module.refresh(profile, ACCOUNT, lock, exploding_post,
                                    no_wait)

    assert result.outcome == refresh_module.TRANSIENT
    assert not os.path.exists(str(lock_file)), \
        'the lock file survived a failed exchange'


# ---------------------------------------------------------------------------
# The short retry profile, and the constant it is pinned against
# ---------------------------------------------------------------------------

def test_the_short_retry_profile_stays_inside_the_lock_lifetime():
    """The transport's own comment computes its default worst case at 155
    seconds. A lock lifetime above that would hold the other contender for
    minutes, so the refresh gets a profile of its own and the lifetime sits
    just clear of ITS worst case.

    This is the assertion that stops the two being changed independently."""
    assert refresh_module.WORST_CASE_SECONDS == (
        refresh_module.REQUEST_TRIES * refresh_module.TRANSPORT_TIMEOUT_SECONDS
        + refresh_module.REQUEST_DELAY_SECONDS)
    assert refresh_module.WORST_CASE_SECONDS < RefreshLock.LIFETIME_SECONDS, \
        'the refresh can outlive the lock that protects it: %d >= %d' % (
            refresh_module.WORST_CASE_SECONDS, RefreshLock.LIFETIME_SECONDS)
    assert refresh_module.REQUEST_TRIES <= 2, \
        'the refresh is back on a long retry ladder'


def test_the_profile_names_the_lock_lifetime_beside_its_arithmetic():
    """Read the source back. A number whose reason is not written next to it is
    a number the next reader will change, and this particular one is load-
    bearing in a way nothing on the surface shows."""
    source = read_source('resources/lib/auth/refresh.py')

    assert 'LIFETIME_SECONDS' in source, \
        'the profile does not name the lock constant it is set against'
    assert '155' in source, \
        "the transport's default worst case is not recorded beside the profile"


def test_the_bounded_wait_outlives_the_lock_lifetime():
    """A contender that waits for less than the lifetime can never be the one
    that breaks a genuinely stuck lock, so the stall would outlast the call and
    reappear on the next one."""
    budget = refresh_module.ADOPT_ATTEMPTS * (
        refresh_module.ACQUIRE_TIMEOUT_SECONDS
        + refresh_module.ADOPT_POLL_SECONDS)
    assert budget > RefreshLock.LIFETIME_SECONDS, \
        'the bounded wait (%s) never reaches the lock lifetime (%s)' % (
            budget, RefreshLock.LIFETIME_SECONDS)


# ---------------------------------------------------------------------------
# Observing rotation in the field without publishing a credential
# ---------------------------------------------------------------------------

def test_the_rotation_log_shows_eight_leading_characters_and_no_more(
        profile, token_file, lock_file, signed_in):
    """Eight characters answers the question -- did it change -- and a log on
    this platform is a file users paste into public forums verbatim."""
    lines = []
    post = RecordingPost(rotated(1, refresh_token='M.C123_BAY.0.U.-Cr' * 8))

    refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file), post,
                           no_wait, log=lines.append)

    assert lines, 'nothing was logged, so rotation cannot be observed at all'
    written = stored(token_file)['refresh_token']
    joined = '\n'.join(lines)
    assert written not in joined
    assert written[:8] in joined
    assert written[:9] not in joined


def test_a_release_that_removed_nothing_is_logged(monkeypatch, profile,
                                                  token_file, lock_file,
                                                  signed_in):
    """The orphan is invisible from inside the add-on unless this says so.

    A lock file that survives its release carries the current session id, so no
    contender breaks it and every one of them waits out its whole acquire
    timeout instead. That looks like slowness, and slowness gets blamed on the
    network. One line makes it name itself.
    """
    lines = []
    post = RecordingPost(rotated(1))

    def always_refuse(path):
        raise PermissionError(13, 'in use by another process')

    monkeypatch.setattr(os, 'unlink', always_refuse)

    lock = new_lock(lock_file)
    # The grace is a wall-clock second in production and this test spends all
    # of it, since the refusal never clears. Shortened on the instance rather
    # than the class: what is under test is that expiry is reported, not how
    # long expiry takes, and a second here would make this the slowest test in
    # the file by an order of magnitude.
    lock.RELEASE_GRACE_SECONDS = 0.02

    result = refresh_module.refresh(profile, ACCOUNT, lock, post,
                                    no_wait, log=lines.append)

    assert result.outcome == refresh_module.SUCCEEDED, \
        'the refresh itself must still succeed; the lock is not its job'
    joined = '\n'.join(lines)
    assert 'lock could not be removed' in joined, \
        'the failed release said nothing:\n%s' % joined
    assert str(lock_file) not in joined and 'lock' in joined, \
        'the message names the path, which sits beside the token file'


def test_the_fingerprint_of_an_absent_token_is_not_an_index_error():
    """A blob with no refresh token reaches the logger on the needs-
    reauthorisation path, and a crash in a log line is a crash."""
    assert refresh_module.fingerprint('') == refresh_module.NO_TOKEN
    assert refresh_module.fingerprint(None) == refresh_module.NO_TOKEN
    assert refresh_module.fingerprint('abcdefghijkl').startswith('abcdefgh')


def read_source(relative):
    with open(os.path.join(REPO_ROOT, relative), 'r', encoding='utf-8') as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# Two contenders, in one process and in two
# ---------------------------------------------------------------------------

def test_two_threads_in_one_process_produce_exactly_one_exchange(
        profile, token_file, lock_file, signed_in):
    """The case that matters here, because the plugin and the service are
    sub-interpreters inside ONE process. Both contenders enter with the same
    blob; exactly one spends the refresh token and the other adopts what it
    wrote."""
    both_ready = threading.Barrier(2)
    outcomes = {}
    failures = []
    exchanges = []

    def contend(name):
        def post(url, fields):
            exchanges.append(name)
            # Slow enough that the loser is genuinely still inside its wait
            # rather than racing the winner's write by luck.
            time.sleep(0.05)
            return rotated(1, access_token='access-by-' + name,
                           refresh_token='rotated-by-' + name)

        try:
            both_ready.wait(10)
            outcomes[name] = refresh_module.refresh(
                profile, ACCOUNT, new_lock(lock_file), post, no_wait,
                acquire_timeout=2)
        except BaseException as problem:     # pragma: no cover - reported
            failures.append('%s: %r' % (name, problem))

    threads = [threading.Thread(target=contend, args=(name,))
               for name in ('plugin', 'service')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)

    assert not failures, failures
    assert len(exchanges) == 1, \
        'both contenders spent the refresh token: %s' % (exchanges,)

    winner = exchanges[0]
    assert stored(token_file)['refresh_token'] == 'rotated-by-' + winner
    for name in ('plugin', 'service'):
        assert outcomes[name].outcome == refresh_module.SUCCEEDED
    loser = 'service' if winner == 'plugin' else 'plugin'
    assert outcomes[loser].adopted is True
    assert outcomes[loser].exchanged is False


CHILD_SOURCE = textwrap.dedent('''
    """Spawned by test_two_processes_adopt_rather_than_both_exchange."""
    import json
    import os
    import sys
    import time

    sys.path.insert(0, sys.argv[1])
    from resources.lib.auth import refresh as refresh_module, store
    from resources.lib.auth.lock import RefreshLock

    profile, account, session, ready_flag, result_path = sys.argv[2:7]

    calls = []


    def post(url, fields):
        calls.append(fields.get('refresh_token'))
        return 200, {'access_token': 'access-by-child',
                     'refresh_token': 'rotated-by-child',
                     'expires_in': 3599}


    def sleep(seconds):
        # The signal goes here rather than before the call, and that ordering
        # is the whole reliability of this test. Every wait in the refresh
        # happens AFTER it has read the store, so a parent that waits for this
        # flag knows the child is holding the old blob and is contending. A
        # flag raised before the call would let the parent's write land first,
        # and the child would then be refreshing an already-fresh token --
        # correct behaviour, but not the behaviour under test.
        if not os.path.exists(ready_flag):
            open(ready_flag, 'w').close()
        time.sleep(min(seconds, 0.02))
        return False


    lock = RefreshLock(store.lock_path(profile, account), session, sleep)
    result = refresh_module.refresh(profile, account, lock, post, sleep,
                                    acquire_timeout=0.3, attempts=12)

    with open(result_path, 'w') as handle:
        json.dump({'outcome': result.outcome,
                   'adopted': result.adopted,
                   'exchanged': result.exchanged,
                   'exchanges': len(calls),
                   'refresh_token': (result.blob or {}).get('refresh_token')},
                  handle)
''')


def test_two_processes_adopt_rather_than_both_exchange(
        tmp_path, profile, token_file, lock_file, signed_in):
    """Kept because it is the case a reader expects, and its absence would read
    as an oversight.

    The one-process case above is the one that matters in Kodi. This one proves
    the same property across a real process boundary, with one spawn and file
    coordination, because the whole suite's budget is about two seconds.
    """
    script = tmp_path / 'contender.py'
    script.write_text(CHILD_SOURCE, encoding='utf-8')
    ready_flag = tmp_path / 'child-is-ready'
    result_path = tmp_path / 'child-result.json'

    winner = new_lock(lock_file)
    assert winner.acquire(1) is True
    released = False

    child = subprocess.Popen([
        sys.executable, str(script), REPO_ROOT, profile, ACCOUNT, SESSION,
        str(ready_flag), str(result_path),
    ])
    try:
        deadline = time.time() + 30
        while not ready_flag.exists() and time.time() < deadline:
            if child.poll() is not None:
                break
            time.sleep(0.01)
        assert ready_flag.exists(), \
            'the child never reported in; it exited %r' % child.poll()

        # The winner finishes its exchange while the child is contending.
        store.write(str(token_file), dict(signed_in,
                                          access_token='access-by-parent',
                                          refresh_token='rotated-by-parent'))
        winner.release()
        released = True

        assert child.wait(60) == 0, 'the child process failed'
    finally:
        if not released:
            winner.release()
        if child.poll() is None:
            child.kill()

    result = json.loads(result_path.read_text(encoding='utf-8'))
    assert result == {
        'outcome': refresh_module.SUCCEEDED,
        'adopted': True,
        'exchanged': False,
        'exchanges': 0,
        'refresh_token': 'rotated-by-parent',
    }


# ---------------------------------------------------------------------------
# A lost race, a dead grant, and a dead network are three different things
# ---------------------------------------------------------------------------

def refused(code, error='invalid_grant'):
    """A refusal in the shape the token endpoint actually sends one.

    The description is a paragraph with the code buried in it, because that is
    the only place the provider puts it -- there is no structured field -- and
    a tidied one-line version would not prove the extraction survives.
    """
    return 400, {
        'error': error,
        'error_description':
            '%s: The provided value for the input parameter refresh_token is '
            'not valid. Trace ID: 0e4a2f1c-1111-2222-3333-444455556666 '
            'Correlation ID: 7f3d9a55-aaaa-bbbb-cccc-ddddeeeeffff Timestamp: '
            '2026-08-23 04:11:22Z\r\n'
            'https://login.microsoftonline.com/error?code=%s'
            % (code, code[len('AADSTS'):]),
        'error_codes': [int(code[len('AADSTS'):])],
    }


def winner_writes_then(token_file, blob, response):
    """A port that writes somebody else's result before answering.

    This is the double-break case in one callable: two contenders both judged
    the lock stale, the other one redeemed the refresh token and wrote while
    this one was mid-request, and the provider then answers this one that the
    grant it was given is not valid -- because it has been rotated.
    """
    def post(url, fields):
        store.write(token_file, blob)
        return response
    return post


def test_an_invalid_grant_whose_store_moved_on_is_adopted_not_a_sign_out(
        profile, token_file, lock_file, signed_in):
    """Half of AUTH-15, and the half that matters.

    The provider said the grant is invalid. The store says the refresh token
    has been replaced since this attempt began. That is a lost race, not a dead
    grant, and turning it into a sign-in prompt converts a harmless collision
    into the exact failure the whole locking design exists to avoid.
    """
    post = winner_writes_then(
        token_file,
        dict(signed_in, access_token='access-by-winner',
             refresh_token='rotated-by-winner'),
        refused('AADSTS700082'))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.SUCCEEDED
    assert result.outcome != refresh_module.NEEDS_REAUTHORISATION
    assert result.adopted is True
    assert result.exchanged is True
    assert result.blob['refresh_token'] == 'rotated-by-winner'
    assert stored(token_file)['refresh_token'] == 'rotated-by-winner'


def test_an_invalid_grant_against_a_byte_identical_stored_token_is_a_dead_grant(
        profile, token_file, lock_file, signed_in):
    """The other half. Same response, same code, same everything except what
    the store says -- and the store is the whole test."""
    post = RecordingPost(refused('AADSTS700082'))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.NEEDS_REAUTHORISATION
    assert result.adopted is False
    assert stored(token_file)['refresh_token'] == 'refresh-token-0', \
        'a refusal changed the stored token'


def test_the_two_invalid_grant_branches_are_told_apart_by_the_store_alone(
        profile, token_file, lock_file, signed_in):
    """Stated as one assertion because it is one idea: the response is not
    evidence, and the disk is."""
    moved_on = refresh_module.refresh(
        profile, ACCOUNT, new_lock(lock_file),
        winner_writes_then(token_file,
                           dict(signed_in, access_token='access-by-winner',
                                refresh_token='rotated-by-winner'),
                           refused('AADSTS700082')),
        no_wait)

    store.write(token_file, dict(signed_in))
    unchanged = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                       RecordingPost(refused('AADSTS700082')),
                                       no_wait)

    assert (moved_on.outcome, unchanged.outcome) == (
        refresh_module.SUCCEEDED, refresh_module.NEEDS_REAUTHORISATION)


def test_a_store_that_moved_on_to_the_same_token_is_still_a_dead_grant(
        profile, token_file, lock_file, signed_in):
    """Byte-identical, so it did not move. A comparison that only checked
    whether the file had been rewritten would pass here and sign nobody out --
    while a genuinely dead grant would then retry forever."""
    post = winner_writes_then(token_file, dict(signed_in),
                              refused('AADSTS700082'))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.NEEDS_REAUTHORISATION


# ---------------------------------------------------------------------------
# A transport failure is not a grant failure (AUTH-16, Pitfall E)
# ---------------------------------------------------------------------------

def transport_failures():
    """Every way the network can fail to produce a protocol answer.

    Each of these must leave the account exactly as it was. A box that starts
    before its Wi-Fi, a router mid-reboot and a captive portal all arrive here,
    and every one of them that produced a sign-in prompt would be asking the
    user to fix something that is already fixing itself.
    """
    def no_route(url, fields):
        raise OSError('[Errno 101] Network is unreachable')

    def name_resolution(url, fields):
        raise OSError('[Errno -2] Name or service not known')

    def captive_portal(url, fields):
        # The HTTP port's sentinel for a body that would not parse as JSON.
        return 200, {'error': device_code.NON_JSON_ERROR}

    def provider_having_a_moment(url, fields):
        return 503, {'error': 'temporarily_unavailable'}

    def provider_internal_error(url, fields):
        return 500, {'error': 'server_error'}

    return [
        pytest.param(no_route, id='no-route'),
        pytest.param(name_resolution, id='name-resolution'),
        pytest.param(captive_portal, id='captive-portal'),
        pytest.param(provider_having_a_moment, id='temporarily-unavailable'),
        pytest.param(provider_internal_error, id='server-error'),
    ]


@pytest.mark.parametrize('post', transport_failures())
def test_a_transport_failure_is_transient_and_marks_nothing(
        post, profile, token_file, lock_file, signed_in):
    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.TRANSIENT
    assert result.outcome != refresh_module.NEEDS_REAUTHORISATION
    assert stored(token_file) == signed_in, \
        'a transport failure changed the stored blob'


# ---------------------------------------------------------------------------
# The refusal is classified through the table plan 03-05 built
# ---------------------------------------------------------------------------

def test_a_dead_grant_is_classified_through_the_failure_table(
        profile, token_file, lock_file, signed_in):
    """One place in the tree knows what a provider code means. The browse
    phase's requirement to distinguish failure states inherits this
    classification rather than inventing a second one."""
    post = RecordingPost(refused('AADSTS53003'))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.outcome == refresh_module.NEEDS_REAUTHORISATION
    assert result.failure == errors.Failure(
        errors.BLOCKED_BY_CONDITIONAL_ACCESS, 'AADSTS53003', True)


def test_an_unmapped_refusal_still_carries_its_bare_code(
        profile, token_file, lock_file, signed_in):
    """`AADSTS700082` is the inactivity expiry -- the very failure the
    proactive refresh exists to prevent -- and it is not in the table. A code a
    person can read off a television and quote is worth more than a friendly
    sentence that hides it."""
    post = RecordingPost(refused('AADSTS700082'))

    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    post, no_wait)

    assert result.failure.outcome == errors.UNMAPPED
    assert result.failure.code == 'AADSTS700082'


def test_a_successful_refresh_carries_no_failure(
        profile, token_file, lock_file, signed_in):
    result = refresh_module.refresh(profile, ACCOUNT, new_lock(lock_file),
                                    RecordingPost(rotated(1)), no_wait)

    assert result.failure is None


# ---------------------------------------------------------------------------
# The startup check (AUTH-16)
# ---------------------------------------------------------------------------

DAY = 86400.0


def blob_issued(days_ago, now=1000000.0, **overrides):
    answer = {'access_token': 'access-token-0',
              'refresh_token': 'refresh-token-0',
              'issued_at': now - days_ago * DAY}
    answer.update(overrides)
    return answer


def test_the_startup_check_skips_a_recently_issued_blob():
    """Refreshing on every start also works and is simpler. It is not free:
    every write is a chance to leave a temporary file behind on a device that
    gets power-cut rather than shut down."""
    assert refresh_module.should_refresh(blob_issued(1), now=1000000.0) is False


def test_the_startup_check_takes_an_old_blob():
    assert refresh_module.should_refresh(blob_issued(80), now=1000000.0) is True


def test_the_startup_check_treats_a_missing_issue_time_as_old():
    """A blob written before the field existed is of unknown age, and unknown
    must mean refresh. Assuming it is fresh is the assumption that ends with an
    expired grant and nothing to show for it."""
    blob = blob_issued(1, now=1000000.0)
    del blob['issued_at']

    assert refresh_module.should_refresh(blob, now=1000000.0) is True


def test_the_startup_check_declines_a_blob_with_nothing_to_refresh():
    """An account that has never signed in has no grant to spend. Answering
    True here would send the service to the network on every start and mark the
    account on every failure."""
    assert refresh_module.should_refresh({}, now=1000000.0) is False
    assert refresh_module.should_refresh({'access_token': 'a'},
                                         now=1000000.0) is False


def test_the_startup_check_takes_a_blob_exactly_on_the_threshold():
    """The boundary belongs on the refreshing side. A blob that is exactly at
    the threshold on one start is past it on the next, so the only thing this
    choice changes is which start does the work -- and the earlier one is the
    one with more of the window left."""
    assert refresh_module.should_refresh(
        blob_issued(refresh_module.REFRESH_AFTER_DAYS,
                    now=1000000.0), now=1000000.0) is True


def test_the_threshold_sits_well_inside_the_ninety_day_window():
    """Not at the edge. A threshold near ninety leaves no room for a device
    that is switched on rarely: the whole point is that a box used once every
    few months still refreshes before the window closes."""
    assert refresh_module.REFRESH_TOKEN_LIFETIME_DAYS == 90
    assert 0 < refresh_module.REFRESH_AFTER_DAYS <= (
        refresh_module.REFRESH_TOKEN_LIFETIME_DAYS / 2), \
        'the threshold (%s days) is not well inside the %s-day window' % (
            refresh_module.REFRESH_AFTER_DAYS,
            refresh_module.REFRESH_TOKEN_LIFETIME_DAYS)


def test_the_threshold_records_its_arithmetic():
    """The number is a judgement, and a judgement with no reasoning beside it
    is a number the next reader will change to a rounder one."""
    source = read_source('resources/lib/auth/refresh.py')
    assert 'REFRESH_TOKEN_LIFETIME_DAYS' in source
    assert 'ninety' in source or '90' in source
