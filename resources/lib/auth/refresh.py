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
"""Refresh one account's token without losing the rotated one, and without
signing anybody out over a race.

Two properties carry this module, and both of them are invisible failures:

  * **The provider replaces the refresh token on every use, and does not revoke
    the old one.** Code that keeps re-sending the original therefore works
    perfectly -- in development, through a two-week test cycle, through a
    release -- until the original reaches its ninety-day lifetime, and then it
    fails for every installation on the same day with no code change to blame.
    The merge that keeps the response's token lives in `store`, so there is one
    implementation of it; what lives here is the discipline of always going
    through that merge, and the test that proves the stored value changed.

  * **A contender that loses the race is told its grant is invalid.** That is
    the same answer a genuinely dead grant produces, and reading it as one signs
    a user out of a working account -- which is precisely the failure the whole
    locking design exists to avoid. The store is re-read from disk and the
    stored token compared byte-for-byte against the one just rejected. That
    comparison is the entire test for which of the two this is.

Nothing here imports a Kodi module and nothing here opens a socket. The HTTP
port is a callable the caller supplies -- `post(url, fields) -> (status, body)`
with `body` already parsed -- and the wait is an injected function that returns
True when Kodi is shutting down. In production that is `Monitor.waitForAbort`;
in a test it is a capped no-op.
"""

import collections
import time

from resources.lib.auth import device_code, errors, store
from resources.lib.auth.lock import RefreshLock

# ---------------------------------------------------------------------------
# The three things a refresh can mean
#
# Three and not two, because "it did not work" is two different events with
# opposite responses. A grant the provider has refused needs a sign-in; a
# network that was not up yet needs nothing at all. Collapsing them asks the
# user to sign in again because their box booted before its Wi-Fi -- which is
# the exact experience the proactive refresh exists to prevent (Pitfall E).
# ---------------------------------------------------------------------------

#: There is a usable access token on disk now. Either this call put it there or
#: another contender did and this call adopted it.
SUCCEEDED = 'succeeded'

#: Nothing worked and nothing changed. Try again later; change no record, show
#: no prompt, and above all do not mark the account.
TRANSIENT = 'transient'

#: The provider refused the grant and the store has not moved on, so this is a
#: dead grant rather than a lost race. Only this outcome may set a
#: needs-reauthorisation mark.
NEEDS_REAUTHORISATION = 'needs_reauthorisation'


#: What `refresh` returns.
#:
#: `outcome`    one of the three above.
#: `blob`       the token blob as it now stands on disk, or {} if there is none.
#: `failure`    an `errors.Failure` when the provider named a refusal, else
#:              None. The renderer turns it into a sentence; this module does
#:              not hold words.
#: `adopted`    True when this call took another contender's freshly-written
#:              token instead of spending one of its own.
#: `exchanged`  True when this call actually went to the network. Distinct from
#:              `adopted`, because a contender can exchange AND then adopt: it
#:              raced through, was told the grant was invalid, re-read the
#:              store and found the winner's token there.
Refreshed = collections.namedtuple('Refreshed',
                                   'outcome blob failure adopted exchanged')

# The grant type for a refresh, per RFC 6749 section 6.
GRANT_TYPE = 'refresh_token'

# ---------------------------------------------------------------------------
# The one response this module has to think hardest about
#
# `invalid_grant` is what the provider answers when the refresh token it was
# handed cannot be redeemed. It is also, word for word, what it answers a
# contender that lost the race: the winner redeemed that token a moment ago and
# the provider rotated it, so the grant is not dead -- it has moved.
#
# Nothing in the response tells the two apart. The store does.
INVALID_GRANT = 'invalid_grant'

# Refusals that say the provider is having a moment rather than that the grant
# is finished. RFC 6749 section 5.2 defines both, and neither is a statement
# about this account.
TRANSIENT_ERRORS = frozenset(('temporarily_unavailable', 'server_error'))

# At and above this the provider is not answering about the grant at all.
SERVER_ERROR_STATUS = 500

# ---------------------------------------------------------------------------
# The short request profile
#
# The transport's own comment computes its worst-case wall time at ITS defaults
# (tries=4, delay=5, backoff=2, timeout=30) as 4*30 + 5 + 10 + 20 = 155
# seconds. A lock whose lifetime covered that would hold the other contender
# for two and a half minutes; a lock whose lifetime did not would break the
# lock of a live, working refresh, which is the double write the lock exists to
# prevent.
#
# Neither is necessary, because a token refresh has no business sitting on a
# retry ladder at all: when it fails it has a defined recovery path, and that
# path is this file. So the refresh gets a profile of its own --
#
#     REQUEST_TRIES * TRANSPORT_TIMEOUT_SECONDS + REQUEST_DELAY_SECONDS
#         = 2 * 30 + 5
#         = 65 seconds
#
# -- and `RefreshLock.LIFETIME_SECONDS` (90) sits twenty-five seconds clear of
# it. THE DEPENDENCY RUNS BOTH WAYS: restoring the transport's default profile
# here moves the worst case back to 155 seconds and silently starts breaking
# live locks, and lowering the lock's lifetime below 65 does the same.
# `tests/test_refresh.py::test_the_short_retry_profile_stays_inside_the_lock_lifetime`
# is what stops the two being changed independently.
#
# These are values for the Kodi layer to hand to the transport's constructor,
# not something this module applies: the HTTP port arrives already built, which
# is what keeps this file free of Kodi and of sockets.
REQUEST_TRIES = 2
REQUEST_DELAY_SECONDS = 5
REQUEST_BACKOFF = 1

# `Request.HTTP_TIMEOUT_SECONDS`, restated rather than imported: the transport
# module imports Kodi, and this package must not.
TRANSPORT_TIMEOUT_SECONDS = 30

WORST_CASE_SECONDS = (REQUEST_TRIES * TRANSPORT_TIMEOUT_SECONDS
                      + REQUEST_DELAY_SECONDS)

#: The lock lifetime the profile above is set against, re-exported so that the
#: coupling is an import a reader can follow rather than a number in a comment
#: they have to go and look up.
LOCK_LIFETIME_SECONDS = RefreshLock.LIFETIME_SECONDS

# ---------------------------------------------------------------------------
# The waiting profile
#
# How long one attempt at the lock waits before reporting that it lost, how
# long the loser then waits before re-reading, and how many times it does that
# before giving up.
#
#     ADOPT_ATTEMPTS * (ACQUIRE_TIMEOUT_SECONDS + ADOPT_POLL_SECONDS)
#         = 3 * (30 + 1)
#         = 93 seconds
#
# which is deliberately just past `RefreshLock.LIFETIME_SECONDS`. A contender
# whose whole budget expired before the lifetime could never be the one to
# break a genuinely stuck lock, so the stall would survive the call and
# reappear on the next one.
# ---------------------------------------------------------------------------
ACQUIRE_TIMEOUT_SECONDS = 30
ADOPT_POLL_SECONDS = 1.0
ADOPT_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# The startup threshold (AUTH-16)
#
# A refresh token lasts ninety days, and the inactivity clock that expires it
# is only reset by using it. A media player can sit unused for months, so the
# service refreshes on Kodi start -- but not on EVERY start. Every write is a
# chance to leave a temporary file behind on a device that gets power-cut
# rather than shut down, and a box that is switched on daily does not need a
# network call and an atomic write each time.
#
# Thirty days, not sixty and not eighty-five:
#
#     REFRESH_TOKEN_LIFETIME_DAYS - REFRESH_AFTER_DAYS = 90 - 30 = 60
#
# days of margin. A threshold near the edge of the window only works for a box
# that is switched on often, which is the case that needs no help at all: a
# device used once every forty-five days would skip a sixty-day threshold on
# one start and find the grant already dead on the next.
# ---------------------------------------------------------------------------
REFRESH_TOKEN_LIFETIME_DAYS = 90
REFRESH_AFTER_DAYS = 30
SECONDS_PER_DAY = 86400

# ---------------------------------------------------------------------------
# Observing rotation without publishing a credential
#
# Eight leading characters answers the only question worth asking in the field
# -- did the stored token change between refreshes -- and answers nothing else.
# A Kodi log is a file users paste into public forums verbatim, so the whole
# token must never be in one; the transport's redactor covers the response
# bodies, and this covers the one line that exists to watch the rotation.
# ---------------------------------------------------------------------------
FINGERPRINT_CHARACTERS = 8
NO_TOKEN = '(none)'


def fingerprint(token):
    """The first eight characters of `token`, or `NO_TOKEN`.

    Tolerating an absent token matters: the needs-reauthorisation path reaches
    the logger with a blob that may have none, and a crash inside a log line is
    still a crash.
    """
    if not token:
        return NO_TOKEN
    return token[:FINGERPRINT_CHARACTERS] + '...'


def refresh(profile_path, account_key, lock, post, sleep,
            client_id=device_code.CLIENT_ID, now=None, log=None,
            acquire_timeout=ACQUIRE_TIMEOUT_SECONDS, attempts=ADOPT_ATTEMPTS):
    """Refresh one account's token. Returns a `Refreshed`.

    `profile_path` is already resolved by the Kodi layer, `lock` is a
    `RefreshLock` on this account's lock file, `post` is the HTTP port and
    `sleep` is the abort-aware wait. Everything Kodi-shaped is injected, which
    is what lets the whole race be driven in a test without a stub library.

    The happy path is acquire, read, exchange, merge, write, release. The
    interesting paths are the two ways this call can end up using somebody
    else's token instead of spending its own, and both of them re-read the
    store FROM DISK rather than trusting anything loaded before the attempt.
    """
    token_file = store.token_path(profile_path, account_key)
    entry = store.read(token_file)
    entry_access = entry.get('access_token')

    if not entry.get('refresh_token'):
        # There is no grant to refresh. Going to the network to be told so
        # costs a round trip and answers nothing, and this is not a race and
        # not a network failure: the only recovery is a sign-in.
        return Refreshed(NEEDS_REAUTHORISATION, entry, None, False, False)

    for _attempt in range(max(1, attempts)):
        if not lock.acquire(acquire_timeout):
            # The cheap path, and the common one. Somebody else is refreshing
            # right now. Wait, then re-read from disk -- not from `entry`,
            # which is a snapshot from before the race began.
            if sleep(ADOPT_POLL_SECONDS):
                # Kodi is going away. Changing nothing is the right answer.
                return Refreshed(TRANSIENT, entry, None, False, False)

            current = store.read(token_file)
            if current.get('access_token') != entry_access:
                # The winner finished. No network call at all.
                return Refreshed(SUCCEEDED, current, None, True, False)
            # Unchanged: the winner may still be in flight. Bounded, not
            # indefinite -- a holder that never finishes must cost this side a
            # defined wait and then a transient answer.
            continue

        try:
            # Under the lock, and re-read here too. Having waited for the lock
            # and got it, whatever was loaded before the acquire is a snapshot
            # from before the previous holder wrote.
            current = store.read(token_file)
            if current.get('access_token') != entry_access:
                return Refreshed(SUCCEEDED, current, None, True, False)
            return _exchange(post, client_id, token_file, current, now, log)
        finally:
            # In a finally, so a raised exchange cannot hold the lock for a
            # whole lifetime -- ninety seconds in which the add-on looks wedged
            # for a reason nobody watching it can see.
            #
            # The answer is read rather than dropped. A release can genuinely
            # fail to remove the file, and the orphan it leaves carries THIS
            # session's identifier, so `_staleness` reads it as fresh and no
            # contender will break it: exactly the ninety wedged seconds the
            # `finally` above is here to prevent, arriving by the other door.
            # Without this line it is invisible until somebody wonders why
            # refreshes are taking their whole acquire timeout.
            #
            # No path in the message. The lock sits beside the token file, and
            # a log on this platform is a file users paste into forums whole.
            if not lock.release() and log is not None:
                log('the refresh lock could not be removed; other contenders '
                    'in this session will wait it out')

    return Refreshed(TRANSIENT, store.read(token_file), None, False, False)


def _exchange(post, client_id, token_file, blob, now, log):
    """One refresh_token grant, merged and written under the caller's lock."""
    used = blob.get('refresh_token')

    try:
        status, body = post(device_code.TOKEN_ENDPOINT, {
            'grant_type': GRANT_TYPE,
            'client_id': client_id,
            'refresh_token': used,
            'scope': device_code.SCOPES,
        })
    except Exception:
        # The port did not come back with a protocol answer at all: no route,
        # a name that would not resolve, a timeout, a proxy that hung up. None
        # of those says anything about the grant, and treating them as if they
        # did is how a router reboot turns into a sign-in prompt (Pitfall E).
        return Refreshed(TRANSIENT, blob, None, False, True)

    if not isinstance(body, dict):
        return Refreshed(TRANSIENT, blob, None, False, True)

    if body.get('access_token'):
        # -- the ordinary success path ------------------------------------
        # Through the store's own merge, so the keep-the-previous-refresh-token
        # rule has exactly one implementation in the tree.
        merged = store.merge_token_response(blob, body, now=now)
        store.write(token_file, merged)
        if log is not None:
            log('token refreshed: refresh token %s -> %s'
                % (fingerprint(used), fingerprint(merged.get('refresh_token'))))
        return Refreshed(SUCCEEDED, merged, None, False, True)

    error = body.get('error') or ''

    if (error == device_code.NON_JSON_ERROR or error in TRANSIENT_ERRORS
            or _is_server_error(status)):
        # The provider did not answer about this grant. A captive portal's
        # login page, a proxy's error page and the provider's own bad half
        # hour all land here, and none of them is evidence about the account.
        return Refreshed(TRANSIENT, blob, None, False, True)

    if error == INVALID_GRANT:
        # THE LOST RACE. Before this can mean "sign in again", the store is
        # re-read FROM DISK -- not from `blob`, which was read before the
        # request went out and cannot know what happened while it was in
        # flight. If the stored refresh token has moved on, the winner
        # redeemed the one this call was carrying and wrote its replacement:
        # adopt it, and prompt nobody.
        #
        # Byte-identical is the only reading that makes this a dead grant. A
        # weaker test -- "has the file been rewritten" -- would pass on a
        # rewrite that stored the same token, and a dead grant would then be
        # retried forever with nothing on screen to say why.
        current = store.read(token_file)
        rotated = current.get('refresh_token')
        if rotated and rotated != used:
            if log is not None:
                log('refresh token %s was already redeemed; adopting %s'
                    % (fingerprint(used), fingerprint(rotated)))
            return Refreshed(SUCCEEDED, current, None, True, True)

    # A refusal the store does not contradict. Route the code through the one
    # table in the tree that knows what a provider code means, so the browse
    # phase inherits this classification rather than inventing a second one.
    return Refreshed(NEEDS_REAUTHORISATION, blob,
                     errors.classify_response(body), False, True)


def _is_server_error(status):
    """True when the status says the provider, not the grant, is the problem."""
    try:
        return int(status) >= SERVER_ERROR_STATUS
    except (TypeError, ValueError):
        return False


def should_refresh(blob, threshold_days=REFRESH_AFTER_DAYS, now=None):
    """Should the startup check refresh this account's token?

    A small predicate rather than part of `refresh`, because the service asks
    it once per account before deciding to do anything at all, and a predicate
    that needs a lock and an HTTP port to answer is one nothing can test.

    Three rules, and the third is the one that is easy to get backwards:

      * No refresh token means there is nothing to refresh with. False -- and
        emphatically not True, which would send the service to the network on
        every start for an account that has never signed in and mark it as
        needing re-authorisation every time.
      * An issue time older than the threshold means refresh.
      * An ABSENT issue time means refresh. A blob written before the field
        existed is of unknown age, and unknown has to mean old: assuming it is
        fresh is the assumption that ends with an expired grant.
    """
    blob = blob or {}
    if not blob.get('refresh_token'):
        return False

    issued_at = blob.get('issued_at')
    if not isinstance(issued_at, (int, float)):
        return True

    if now is None:
        now = time.time()
    return (now - issued_at) >= threshold_days * SECONDS_PER_DAY
