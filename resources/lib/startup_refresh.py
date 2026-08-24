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
"""Keep the user signed in without ever asking them anything (AUTH-16, AUTH-17).

The refresh token dies after ninety days of inactivity and a media player is
exactly the kind of application that sits unused for months. A refresh at Kodi
start, well inside that window, is what makes "stays signed in" true rather than
aspirational.

The constraint that shapes the rest is *when* this runs. At boot, with nobody in
front of the television and possibly a film already playing, there is no context
for anything this code could ask -- so it may not ask. It refreshes silently,
and when it cannot, it records a marker that the account list renders as a row
the user can choose to act on. That row is the entire channel between this file
and a person.

Four rules follow, and each has an assertion behind it in
`tests/test_startup_refresh.py`:

  * **Only a provider grant refusal writes the marker.** A box starting at boot
    frequently has no network yet, and every failure looks alike from the
    response alone. A transport failure that recorded the marker would produce a
    sign-in prompt after a router reboot, which is the exact experience the
    proactive refresh exists to prevent (Pitfall E, T-03-47). The three-way
    classification that tells them apart is `resources/lib/auth/refresh.py`'s and
    is not restated here.

  * **The marker goes on the account record, never into the token file.** An
    unreadable token file is one of the failure modes being signalled; writing
    the marker into it would be writing into the thing that is broken (T-03-50).

  * **Not every start.** `refresh.should_refresh` is the threshold, and the
    common case -- a box switched on daily -- costs no request and no write at
    all. Every write is a chance to leave a temporary file behind on a device
    that is power-cut rather than shut down.

  * **The attempt is bounded.** A small number of passes with the abort-aware
    wait between them (T-03-48). A service that retries indefinitely is a
    service that is still running when the user starts a film.

The refresh goes through the same per-account lock the plugin takes. Kodi
starting while the user opens the add-on immediately is not an exotic race; it
is the ordinary one, and it is why the lock exists (AUTH-20, T-03-49).

`check_accounts` takes every Kodi-shaped thing by injection -- the profile path,
the lock factory, the HTTP port, the abort-aware wait, the record writer and the
notifier -- so the whole of the behaviour above is driven in a test without a
stub Kodi library. `StartupRefreshService` is the other half: it produces those
arguments and is the only part of this file that knows Kodi exists.

This module lives in this repository's own source rather than inside the
vendored tree because it is new behaviour, not a modification to somebody else's
file, and keeping it out of the vendored package keeps the modification record
shorter. The layering phase will move it under the Kodi-facing package it
establishes; that move is a rename, not a redesign.
"""

from resources.lib.auth import device_code, refresh, store

# ---------------------------------------------------------------------------
# The marker (AUTH-17)
# ---------------------------------------------------------------------------
#
# Written onto the account record when, and only when, a refresh comes back as
# a provider grant refusal. The account list reads the same key and renders that
# account with a distinct label whose default action is signing in again.
#
# The literal is written out twice -- here and in `ui/addon.py` -- rather than
# imported, because importing the account list would drag every dialog in the
# add-on into the service's import closure and turn AUTH-17's static assertion
# red. Two literals that must be equal and are not checked are two literals that
# will differ, so
# `tests/test_startup_refresh.py::test_the_marker_key_is_the_one_the_account_list_reads`
# holds the join.
NEEDS_REAUTH_KEY = 'needs_reauth'

# ---------------------------------------------------------------------------
# The two outcomes that are this module's own
#
# The other three -- SUCCEEDED, TRANSIENT, NEEDS_REAUTHORISATION -- are
# `refresh`'s, and are returned unchanged so that a caller reading these results
# is reading the same vocabulary the rest of the auth package speaks.
# ---------------------------------------------------------------------------

#: The threshold said no. No request was made and nothing was written. This is
#: the common case and it must stay the cheap one.
SKIPPED = 'skipped'

#: The check could not even get as far as asking: a record with no id, a key the
#: store refuses as a filename, a record write that failed. Not evidence about
#: the grant, so it records nothing -- and not retried either, because a crash
#: repeated three times is still a crash.
ERRORED = 'errored'

# ---------------------------------------------------------------------------
# The bound (T-03-48)
#
# Three passes with a twenty-second abort-aware wait between them. The number is
# set by Wi-Fi association rather than by taste: a television that has just been
# switched on can take ten to twenty seconds to get a route, and a single try
# would miss that window every time on the devices that need this most.
#
# The lock budget is deliberately shorter than the plugin's. `refresh.refresh`
# defaults to three acquire attempts of thirty seconds because a plugin
# invocation has a user waiting on it and must eventually break a genuinely
# stuck lock. This caller has the opposite incentive: if somebody else holds the
# lock, somebody else is already refreshing this account, and the right answer
# is to come back on the next pass rather than to contend. One attempt, ten
# seconds.
#
# Worst case for one account, on a network that accepts connections and then
# never answers:
#
#     PASSES * (ACQUIRE_TIMEOUT_SECONDS + refresh.WORST_CASE_SECONDS)
#         + (PASSES - 1) * RETRY_DELAY_SECONDS
#         = 3 * (10 + 65) + 2 * 20
#         = 265 seconds
#
# The boot case this exists for is far cheaper: with no route at all a connect
# fails immediately, so the run is dominated by the two waits and finishes in
# about forty seconds.
# ---------------------------------------------------------------------------
PASSES = 3
RETRY_DELAY_SECONDS = 20
ACQUIRE_TIMEOUT_SECONDS = 10
LOCK_ATTEMPTS = 1

#: The account-list label the notification reuses. The toast and the row say the
#: same words on purpose: they are the same fact reaching the user by two routes,
#: and a second string would let them drift apart.
SIGN_IN_NEEDED_STRING = 30043


def _log(log, message):
    if log is not None:
        log(message)


def _account_key(account):
    """The key this account's files on disk are named by.

    The subject claim from the identity token, recorded as the record's id when
    the account was added. Read rather than derived, and deliberately not
    defaulted: a record with no id is a record this check cannot act on, and
    inventing a key for it would read somebody else's token file.
    """
    return '%s' % (account['id'],)


def _mark(account, save_account, notify, log):
    """Record the marker and, at most, raise a notification.

    A copy with one key added, never a replacement: the drives list is what
    every row in the account list and every stored export references, and a
    record rebuilt from scratch here would take it with it.
    """
    marked = dict(account)
    marked[NEEDS_REAUTH_KEY] = True
    save_account(marked)
    _log(log, 'startup refresh: account %s needs re-authorisation'
              % _account_key(account))
    if notify is not None:
        notify(marked)


def _clear(account, save_account, log):
    """Take the marker off a record whose grant works again.

    Re-authorising through the plugin already clears it, so this is for the
    marker that should never have been written -- and a marker that outlives the
    failure it recorded asks the user to sign in again for an account that is
    working.
    """
    cleared = dict(account)
    cleared.pop(NEEDS_REAUTH_KEY, None)
    save_account(cleared)
    _log(log, 'startup refresh: account %s recovered; marker cleared'
              % _account_key(account))


def _check_one(profile, account, account_key, lock_for, post, wait,
               save_account, client_id, log, notify, now):
    """One account's refresh, classified. Returns an outcome."""
    try:
        result = refresh.refresh(
            profile, account_key, lock_for(profile, account_key), post, wait,
            client_id=client_id, now=now, log=log,
            acquire_timeout=ACQUIRE_TIMEOUT_SECONDS, attempts=LOCK_ATTEMPTS)
    except Exception as error:
        # Not a classification. `refresh` already turns every answer the
        # protocol can give into one of its three outcomes, so anything that
        # escapes it is this code failing rather than the grant.
        _log(log, 'startup refresh: account %s could not be checked: %s'
                  % (account_key, error))
        return ERRORED

    try:
        if result.outcome == refresh.NEEDS_REAUTHORISATION:
            _mark(account, save_account, notify, log)
        elif result.outcome == refresh.SUCCEEDED and account.get(NEEDS_REAUTH_KEY):
            _clear(account, save_account, log)
    except Exception as error:
        # The refresh's own answer stands; only the record write failed. Saying
        # so and returning the real outcome keeps the classification honest, and
        # the next start writes it again.
        _log(log, 'startup refresh: account %s: could not write the record: %s'
                  % (account_key, error))

    return result.outcome


def check_accounts(profile, accounts, lock_for, post, wait, save_account,
                   client_id=device_code.CLIENT_ID, log=None, notify=None,
                   now=None, passes=PASSES, delay=RETRY_DELAY_SECONDS,
                   threshold_days=refresh.REFRESH_AFTER_DAYS):
    """Refresh every account whose stored grant is older than the threshold.

    Returns `{account id: outcome}` for every account reached. An account
    missing from the result is one a shutdown arrived before.

    `accounts` is what `AccountManager.get_accounts` returns; `lock_for(profile,
    key)` builds the same `RefreshLock` the plugin takes; `post` is the HTTP
    port; `wait(seconds)` is the abort-aware sleep and returns True when Kodi is
    going away; `save_account(record)` is the only write this function makes to
    a record; `notify(record)` raises the one non-modal notification the service
    is permitted, and may be None.

    The due set is decided once, up front, so the retry passes cannot go back to
    the network for an account the threshold already excused. Accounts are
    independent by construction: one failing changes nothing about the next.
    """
    outcomes = {}

    # A fast restart can have Kodi shutting down before the service is even up.
    # The loop below checks this again per account; this one is so the whole
    # thing costs nothing at all in that case.
    if wait(0):
        return outcomes

    pending = []
    for account_id in sorted(accounts):
        account = accounts[account_id]
        try:
            account_key = _account_key(account)
            blob = store.read(store.token_path(profile, account_key))
        except Exception as error:
            _log(log, 'startup refresh: skipping an unreadable account record: '
                      '%s' % error)
            outcomes[account_id] = ERRORED
            continue

        if not refresh.should_refresh(blob, threshold_days=threshold_days,
                                      now=now):
            outcomes[account_id] = SKIPPED
            continue

        pending.append((account_id, account, account_key))

    for attempt in range(max(1, passes)):
        if attempt and wait(delay):
            # Kodi is going away between passes. Whatever is still pending is
            # transient, and transient means the next start tries again.
            break

        retry = []
        for account_id, account, account_key in pending:
            if wait(0):
                return outcomes
            outcome = _check_one(profile, account, account_key, lock_for, post,
                                 wait, save_account, client_id, log, notify,
                                 now)
            outcomes[account_id] = outcome
            if outcome == refresh.TRANSIENT:
                retry.append((account_id, account, account_key))

        pending = retry
        if not pending:
            break

    return outcomes


class StartupRefreshService(object):
    """The Kodi half: the arguments `check_accounts` needs, and nothing else.

    Shaped like the other four services so the entry point reads as one list --
    a `name`, a `start` and a `stop` -- but it is a keepalive rather than a
    listener. `ServiceUtil.run` starts each service once in its own daemon
    thread, so `start` returning is the whole of its lifetime, and running there
    rather than before the runner is what keeps the download and source servers
    from waiting on a token exchange before they can bind a port.

    `stop` has nothing to close. The only two things this can be inside when a
    shutdown arrives are the abort-aware wait, which returns immediately, and
    one HTTP request, which the transport bounds at thirty seconds.
    """

    name = 'startup-refresh'

    def __init__(self, provider_class):
        self._provider_class = provider_class

    def _refresh_port(self, provider):
        """The transport for the startup refresh, on the pinned profile.

        THE PROFILE IS NOT A DETAIL, and it is pinned here for the same reason
        it is pinned in the provider: `refresh.REQUEST_TRIES`,
        `REQUEST_DELAY_SECONDS` and `REQUEST_BACKOFF` bound one exchange at
        2 * 30 + 5 = 65 seconds, and `RefreshLock.LIFETIME_SECONDS` is 90
        because of that arithmetic and nothing else. On the transport's own
        defaults the worst case is 155 seconds, and a refresh that outlives the
        lock lifetime is a live lock the plugin is then entitled to break --
        which is the double write the lock exists to prevent (T-03-49).
        `tests/test_auth_gates.py::test_refresh_transport_is_built_from_the_pinned_profile`
        sweeps this file as well as the provider's.
        """
        return provider._post_port(tries=refresh.REQUEST_TRIES,
                                   delay=refresh.REQUEST_DELAY_SECONDS,
                                   backoff=refresh.REQUEST_BACKOFF)

    def start(self):
        # Imported here rather than at module scope so the behaviour above can
        # be driven without a stub Kodi library, exactly as the auth package is.
        from resources.lib.kodi import auth_context
        from resources.lib.vendor.clouddrive_common.account import AccountManager
        from resources.lib.vendor.clouddrive_common.remote.provider import (
            Provider, resolve_client_id)
        from resources.lib.vendor.clouddrive_common.ui.logger import Logger
        from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils

        if auth_context.aborted():
            # A fast restart: Kodi is already going away. The check must not
            # begin, and this is before the profile lookup and the database
            # open so that it costs nothing when it does not.
            return

        # The same resolution the plugin and the other services use, so the
        # service and the plugin read one account database and one token store.
        profile = auth_context.profile_path()
        manager = AccountManager(profile)
        accounts = manager.get_accounts()
        if not accounts:
            return

        provider = self._provider_class()

        def notify(account):
            """The only user-facing surface this service is permitted.

            A toast: it returns immediately, it takes no input and it cannot sit
            over a film waiting for somebody to press a button. The account list
            is still the channel that carries the fact; this only says that
            there is something in it to look at.
            """
            KodiUtils.show_notification(
                '%s: %s' % (account.get('name') or account.get('id'),
                            KodiUtils.localize(SIGN_IN_NEEDED_STRING)))

        outcomes = check_accounts(
            profile, accounts,
            # The plugin's own lock construction rather than a second copy of
            # it: one implementation of "which file, whose session, which wait"
            # is what makes the two processes contend for the same lock at all.
            Provider._lock_for,
            self._refresh_port(provider),
            auth_context.wait,
            manager.save_account,
            client_id=resolve_client_id(),
            log=auth_context.log,
            notify=notify)

        Logger.notice('Service \'%s\' finished: %s' % (self.name, outcomes))

    def stop(self):
        pass
