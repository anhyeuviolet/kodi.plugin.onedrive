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
"""The startup keepalive, and the one thing it must never do.

The refresh token dies after ninety days of inactivity and a media player is
exactly the kind of application that sits unused for months, so the service
spends the grant at Kodi start to reset that clock. Everything difficult about
it follows from *when* it runs: at boot, with nobody in front of the television,
frequently before the box has a network.

Two assertions carry this file.

`test_a_transport_failure_marks_nothing_and_changes_nothing` is the first. Every
failure looks alike from the response alone, and a service that treats "the
Wi-Fi was not up yet" as "your grant is dead" asks the user to sign in again
after a router reboot -- which is the exact experience the proactive refresh
exists to prevent (Pitfall E). Only a provider grant refusal may write the
marker.

`test_the_module_opens_nothing_and_waits_on_nothing_blind` is the second, and it
is static rather than behavioural because the rule it enforces cannot be checked
by running: a dialog three calls deep in a path a test never takes is still a
dialog over whatever the user was watching.

Nothing here imports a Kodi module and nothing here opens a socket. The HTTP
port is the injected `post(url, fields) -> (status, body)` callable the auth
package already takes, the wait is the injected abort-aware sleep, and the
account records are plain dictionaries in the shape `AccountManager` stores.
"""

import ast
import time

import pytest

from gatelib import read

from resources.lib import startup_refresh
from resources.lib.auth import refresh as refresh_module, store
from resources.lib.auth.lock import RefreshLock

# One Kodi session for every contender, because the plugin and the service read
# the same value out of the home window.
SESSION = 'bbbbbbbbbbbb4bbbbbbbbbbbbbbbbbbb'

# Two subject claims, which is what keys an account's files on disk.
FIRST = 'AAAAAAAAAAAAAAAAAAAAAJ1zzz-first_account'
SECOND = 'AAAAAAAAAAAAAAAAAAAAAJ1zzz-second_account'

# A fixed clock. Every age in this file is expressed against it, so a test that
# means "older than the threshold" says so rather than encoding a date.
NOW = 2000000000.0
DAY = refresh_module.SECONDS_PER_DAY

# The reader of the marker this module writes. The two files name nothing of
# each other's contents except this key, so the join is held by an assertion or
# it is not held.
ACCOUNT_LIST = 'resources/lib/vendor/clouddrive_common/ui/addon.py'

MODULE = 'resources/lib/startup_refresh.py'


def no_wait(seconds):
    """The injected sleep in the shape production uses: True means abort.

    Capped rather than skipped, so a caller polling against a real deadline
    waits rather than spins.
    """
    time.sleep(min(seconds, 0.01))
    return False


def aborting_wait(seconds):
    """Kodi is going away. Every wait in this path has to honour it."""
    return True


class Recorder(object):
    """The `save_account` port, which is the only write this module makes to a
    record.

    Holding the calls rather than a final state is deliberate: "wrote nothing"
    and "wrote the same thing back" are different answers, and only one of them
    is correct on a transport failure.
    """

    def __init__(self):
        self.saved = []

    def __call__(self, account):
        self.saved.append(dict(account))


class Refusing(object):
    """A port that never reaches the provider at all.

    No route, a name that would not resolve, a proxy that hung up: none of them
    says anything about the grant.
    """

    def __init__(self, error=None):
        self.calls = []
        self.error = error or OSError('no route to host')

    def __call__(self, url, fields):
        self.calls.append((url, dict(fields)))
        raise self.error


class Never(object):
    """A port whose being called is itself the failure."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, fields):
        self.calls.append((url, dict(fields)))
        raise AssertionError(
            'the startup check went to the network for an account whose '
            'stored token is younger than the threshold')


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / 'addon_data'
    path.mkdir()
    store.accounts_dir(str(path), create=True)
    return str(path)


def record(key, **extra):
    """An account record in the shape AccountManager stores.

    One drive, because /me/drive answers with the default drive and only that.
    """
    account = {'id': key, 'name': key + '@example.invalid',
               'drives': [{'id': 'drive-' + key, 'name': 'OneDrive'}]}
    account.update(extra)
    return account


def stored(profile, key, age_days, token='refresh-token-0'):
    """A blob in the state a completed sign-in leaves behind, aged `age_days`."""
    blob = {
        'token_type': 'Bearer',
        'scope': 'https://graph.microsoft.com/Files.Read openid profile',
        'expires_in': 3655,
        'access_token': 'access-token-for-' + key,
        'refresh_token': token,
        'date': NOW - age_days * DAY,
        'issued_at': NOW - age_days * DAY,
    }
    store.write(store.token_path(profile, key), blob)
    return blob


def locks(profile, account_key):
    return RefreshLock(store.lock_path(profile, account_key), SESSION, no_wait)


def check(profile, accounts, post, wait=no_wait, save=None, **kwargs):
    """`check_accounts` with the ports every test wires the same way."""
    kwargs.setdefault('delay', 0)
    kwargs.setdefault('now', NOW)
    return startup_refresh.check_accounts(
        profile, accounts, locks, post, wait,
        save if save is not None else Recorder(), **kwargs)


def on_disk(profile, key):
    return store.read(store.token_path(profile, key))


# ---------------------------------------------------------------------------
# The threshold (AUTH-16)
# ---------------------------------------------------------------------------

def test_a_recently_issued_token_costs_no_request(profile):
    stored(profile, FIRST, age_days=1)
    post = Never()
    save = Recorder()

    outcomes = check(profile, {FIRST: record(FIRST)}, post, save=save)

    assert outcomes == {FIRST: startup_refresh.SKIPPED}
    assert post.calls == [], 'the common case must cost no request at all'
    assert save.saved == [], 'a skipped account must not be rewritten'


def test_an_account_with_no_stored_grant_is_skipped_without_a_marker(profile):
    store.write(store.token_path(profile, FIRST), {'access_token': 'orphan'})
    post = Never()
    save = Recorder()

    outcomes = check(profile, {FIRST: record(FIRST)}, post, save=save)

    assert outcomes == {FIRST: startup_refresh.SKIPPED}, (
        'an account with nothing to refresh with must be skipped. Sending it '
        'to the network on every start would mark it as needing '
        're-authorisation every time, which is a sign-in prompt for an account '
        'that has simply never been signed in')
    assert save.saved == []


def test_an_old_token_is_refreshed_and_the_stored_grant_moves(
        profile, fake_endpoint, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    before = on_disk(profile, FIRST)
    post = fake_endpoint(responses.refresh())

    outcomes = check(profile, {FIRST: record(FIRST)}, post)

    assert outcomes == {FIRST: refresh_module.SUCCEEDED}
    after = on_disk(profile, FIRST)
    assert after['refresh_token'] != before['refresh_token'], (
        'the provider rotates the refresh token on every use and does not '
        'revoke the old one, so a startup check that leaves the stored value '
        'alone works until the original reaches ninety days and then fails '
        'everywhere on the same day')
    assert after['access_token'] != before['access_token']


def test_a_blob_with_no_issue_time_is_treated_as_old(
        profile, fake_endpoint, responses):
    blob = stored(profile, FIRST, age_days=1)
    del blob['issued_at']
    store.write(store.token_path(profile, FIRST), blob)
    post = fake_endpoint(responses.refresh())

    outcomes = check(profile, {FIRST: record(FIRST)}, post)

    assert outcomes == {FIRST: refresh_module.SUCCEEDED}, (
        'a blob written before the field existed is of unknown age, and '
        'unknown has to mean old')


# ---------------------------------------------------------------------------
# The failure that must not reach the user (Pitfall E, T-03-47)
# ---------------------------------------------------------------------------

def test_a_transport_failure_marks_nothing_and_changes_nothing(profile):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    before = on_disk(profile, FIRST)
    save = Recorder()
    notified = []

    outcomes = check(profile, {FIRST: record(FIRST)}, Refusing(), save=save,
                     notify=notified.append)

    assert outcomes == {FIRST: refresh_module.TRANSIENT}
    assert save.saved == [], (
        'a box that booted before its network was up recorded a marker. The '
        'next thing the user sees is a request to sign in again for an account '
        'that is not broken')
    assert notified == [], 'nothing failed that a person can do anything about'
    assert on_disk(profile, FIRST) == before


def test_a_grant_failure_marks_the_record_and_leaves_the_token_file_alone(
        profile, fake_endpoint, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    token_file = store.token_path(profile, FIRST)
    with open(token_file, 'rb') as handle:
        before = handle.read()
    save = Recorder()
    notified = []
    post = fake_endpoint(responses.terminal(
        code='invalid_grant',
        description='AADSTS700082: The refresh token has expired due to '
                    'inactivity.'))

    outcomes = check(profile, {FIRST: record(FIRST)}, post, save=save,
                     notify=notified.append)

    assert outcomes == {FIRST: refresh_module.NEEDS_REAUTHORISATION}
    assert len(save.saved) == 1, 'the marker is one record write and no more'
    assert save.saved[0][startup_refresh.NEEDS_REAUTH_KEY] is True
    assert save.saved[0]['id'] == FIRST
    assert save.saved[0]['drives'] == record(FIRST)['drives'], (
        'the marker was written by replacing the record rather than by adding '
        'a key to it; the drive every list row and every stored export '
        'references has gone with it')

    with open(token_file, 'rb') as handle:
        assert handle.read() == before, (
            'the marker went into the token file. An unreadable token file is '
            'one of the failure modes being signalled, so the marker must go '
            'somewhere that is still readable when it happens')
    assert len(notified) == 1, (
        'a non-modal notification is the only user-facing surface the service '
        'is permitted, and this is the one failure worth raising it for')


def test_a_stale_marker_is_cleared_when_the_grant_works_again(
        profile, fake_endpoint, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    marked = record(FIRST, **{startup_refresh.NEEDS_REAUTH_KEY: True})
    save = Recorder()

    outcomes = check(profile, {FIRST: marked},
                     fake_endpoint(responses.refresh()), save=save)

    assert outcomes == {FIRST: refresh_module.SUCCEEDED}
    assert len(save.saved) == 1
    assert startup_refresh.NEEDS_REAUTH_KEY not in save.saved[0], (
        'a marker that outlives the failure it recorded asks the user to sign '
        'in again for an account that is working')


def test_a_working_account_is_not_rewritten(profile, fake_endpoint, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    save = Recorder()

    check(profile, {FIRST: record(FIRST)},
          fake_endpoint(responses.refresh()), save=save)

    assert save.saved == [], (
        'a successful refresh rewrote a record that had nothing to change. '
        'Every write is a chance to leave a temporary file behind on a device '
        'that is power-cut rather than shut down')


# ---------------------------------------------------------------------------
# Accounts are independent
# ---------------------------------------------------------------------------

def test_one_failing_account_does_not_prevent_the_other_refreshing(
        profile, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1,
           token='refresh-token-first')
    stored(profile, SECOND, age_days=refresh_module.REFRESH_AFTER_DAYS + 1,
           token='refresh-token-second')
    save = Recorder()

    def post(url, fields):
        if fields['refresh_token'] == 'refresh-token-first':
            return responses.terminal(
                code='invalid_grant',
                description='AADSTS700082: expired due to inactivity.')
        return responses.refresh()

    outcomes = check(profile,
                     {FIRST: record(FIRST), SECOND: record(SECOND)},
                     post, save=save)

    assert outcomes == {FIRST: refresh_module.NEEDS_REAUTHORISATION,
                        SECOND: refresh_module.SUCCEEDED}
    assert on_disk(profile, SECOND)['refresh_token'] == 'synthetic-refresh-token-2'
    assert on_disk(profile, FIRST)['refresh_token'] == 'refresh-token-first'
    assert [entry['id'] for entry in save.saved] == [FIRST]


def test_a_record_the_check_cannot_read_does_not_stop_the_run(
        profile, fake_endpoint, responses):
    stored(profile, SECOND, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    save = Recorder()

    outcomes = check(profile,
                     {FIRST: {'name': 'a record with no id at all'},
                      SECOND: record(SECOND)},
                     fake_endpoint(responses.refresh()), save=save)

    assert outcomes[SECOND] == refresh_module.SUCCEEDED
    assert outcomes[FIRST] == startup_refresh.ERRORED
    assert save.saved == [], (
        'a record that could not be read is not evidence that a grant is dead')


# ---------------------------------------------------------------------------
# The attempt is bounded (T-03-48)
# ---------------------------------------------------------------------------

def test_the_retry_is_bounded(profile):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    post = Refusing()

    outcomes = check(profile, {FIRST: record(FIRST)}, post)

    assert outcomes == {FIRST: refresh_module.TRANSIENT}
    assert len(post.calls) == startup_refresh.PASSES, (
        'the startup check tried %d times against a bound of %d. A service '
        'that retries indefinitely is a service that is still running when the '
        'user starts a film' % (len(post.calls), startup_refresh.PASSES))
    assert 1 < startup_refresh.PASSES <= 4, (
        'the bound is %d. One try does not survive a Wi-Fi association that '
        'takes ten seconds; five is a retry loop wearing a bound as a disguise'
        % startup_refresh.PASSES)


def test_only_the_accounts_that_failed_are_retried(profile, responses):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1,
           token='refresh-token-first')
    stored(profile, SECOND, age_days=refresh_module.REFRESH_AFTER_DAYS + 1,
           token='refresh-token-second')
    seen = []

    def post(url, fields):
        seen.append(fields['refresh_token'])
        if fields['refresh_token'] == 'refresh-token-first':
            raise OSError('no route to host')
        return responses.refresh()

    check(profile, {FIRST: record(FIRST), SECOND: record(SECOND)}, post)

    assert seen.count('refresh-token-second') == 1, (
        'an account that already succeeded was refreshed again on the retry '
        'pass, which spends a grant for nothing and writes the store twice')
    assert seen.count('refresh-token-first') == startup_refresh.PASSES


def test_a_shutdown_stops_the_run_where_it_stands(profile):
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    post = Refusing()
    save = Recorder()

    outcomes = check(profile, {FIRST: record(FIRST)}, post,
                     wait=aborting_wait, save=save)

    assert outcomes == {}, (
        'Kodi was already shutting down and the check ran anyway. A fast '
        'restart is exactly when that happens')
    assert post.calls == []
    assert save.saved == []


def test_a_shutdown_between_passes_stops_the_retry(profile):
    """The wait between passes has to be the abort-aware one AND its answer has
    to be read.

    Only the delay reports the shutdown here. A first draft of this test scripted
    a queue of answers instead, and the per-account `wait(0)` consumed the True
    one pass later and stopped the run anyway -- so a version that called the
    delay and threw its answer away passed. Distinguishing the two guards by
    their argument is what makes this assertion about the one it names.
    """
    stored(profile, FIRST, age_days=refresh_module.REFRESH_AFTER_DAYS + 1)
    post = Refusing()
    delays = []

    def wait(seconds):
        if seconds:
            delays.append(seconds)
            return True
        return False

    outcomes = check(profile, {FIRST: record(FIRST)}, post, wait=wait,
                     delay=startup_refresh.RETRY_DELAY_SECONDS)

    assert outcomes == {FIRST: refresh_module.TRANSIENT}
    assert delays == [startup_refresh.RETRY_DELAY_SECONDS], (
        'the pause between passes was not the abort-aware wait, or it was not '
        'given the retry delay: %r' % (delays,))
    assert len(post.calls) == 1, (
        'the retry carried on through a shutdown that the wait between passes '
        'had already reported')


# ---------------------------------------------------------------------------
# What the service may never do (AUTH-17, T-03-46)
# ---------------------------------------------------------------------------

def test_the_module_opens_nothing_and_waits_on_nothing_blind():
    """Static, because running cannot prove it.

    A dialog three calls deep in a path no test takes is still a dialog over
    whatever the user was watching. `time.sleep` and `xbmc.sleep` are the same
    kind of fault: both ignore the abort flag, so a shutdown waits for them.
    """
    tree = ast.parse(read(MODULE), filename=MODULE)

    dialogs = sorted({node.lineno for node in ast.walk(tree)
                      if isinstance(node, ast.Attribute)
                      and node.attr.startswith('Dialog')}
                     | {node.lineno for node in ast.walk(tree)
                        if isinstance(node, ast.Name)
                        and node.id.startswith('Dialog')})
    assert not dialogs, (
        '%s names a dialog class at line(s) %r. The service runs at Kodi start '
        'with nobody in front of the television' % (MODULE, dialogs))

    blind = sorted({node.lineno for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'sleep'})
    assert not blind, (
        '%s sleeps at line(s) %r without going through the abort-aware wait. '
        'Neither time.sleep nor xbmc.sleep observes the shutdown flag'
        % (MODULE, blind))


def test_the_marker_key_is_the_one_the_account_list_reads():
    """The whole coupling between the writer and the reader, in one assertion.

    Neither file imports the other -- the account list lives in the vendored
    tree and importing it here would drag every dialog in the add-on into the
    service's import closure -- so the key is written out twice. Two literals
    that must be equal and are not checked are two literals that will differ.
    """
    tree = ast.parse(read(ACCOUNT_LIST), filename=ACCOUNT_LIST)
    values = [node.value.value for node in ast.walk(tree)
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name)
                      and target.id == 'NEEDS_REAUTH_KEY'
                      for target in node.targets)
              and isinstance(node.value, ast.Constant)]
    assert len(values) == 1, (
        '%s defines NEEDS_REAUTH_KEY %d times; expected exactly one, so this '
        'assertion knows which one it is checking'
        % (ACCOUNT_LIST, len(values)))
    assert values[0] == startup_refresh.NEEDS_REAUTH_KEY, (
        'the service writes %r onto the account record and the account list '
        'reads %r. The row would never render, and the only channel the '
        'service has to a user would be silently dead'
        % (startup_refresh.NEEDS_REAUTH_KEY, values[0]))
