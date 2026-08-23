#!/usr/bin/env python3
"""Sign in against the live identity provider **through the add-on's own auth
package**, then refresh twice and watch the refresh token rotate.

This is not a second implementation of the flow. Everything the protocol does
here is done by `resources/lib/auth/` -- the same modules that ship inside the
add-on -- and this file supplies only the two things that package deliberately
refuses to contain: an HTTP port, and a place to put the result.

    request_device_code / poll_once / next_interval   device_code
    read_identity_claims                              device_code
    merge_token_response / write / token_path         store
    the whole refresh, its lock and its adopt path    refresh + lock
    the failure-code table                            errors

That distinction is the entire point of running this. A harness that reimplemented
the flow would prove the provider works and would prove nothing whatever about the
code that ships, and the shipped code has so far only ever spoken to a fake endpoint.

Why off the television first: if sign-in fails here it is a protocol problem, and
if it fails on the television after passing here it is a Kodi problem. One session
that does both gives a failure that could be either.

WHAT COMES OUT OF THIS, and what has to be written down afterwards:

  * the granted scope string, verbatim, including its ordering -- it differs by
    account class in membership AND order, so any future check on it has to be
    written against a measured value rather than against the requested string
  * whether the identity token carries a usable `name` claim for this account,
    and what the subject claim's shape is
  * the drive owner's display name from the default-drive endpoint -- the
    fallback the label path uses when `name` is absent, whose field was never
    transcribed from the original spike
  * the `expires_in` returned for each of the three tokens
  * the three refresh-token prefixes, in order

THE STOP CONDITION: if any two of the three refresh-token prefixes match, the
rotation is not reaching disk. Stop and fix it. That is the phase's
highest-consequence requirement and its breakage is invisible for ninety days.

Real credentials touch the disk while this runs. They are written to a scratch
directory OUTSIDE this repository -- never to a Kodi profile -- and removed
again at the end unless --keep-tokens says otherwise. Only eight-character
prefixes are ever printed.

Usage:
    python .planning/research/live_sign_in.py
    python .planning/research/live_sign_in.py --stop-after-code
    python .planning/research/live_sign_in.py --client-id <GUID> --keep-tokens
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# The shipped package, imported from the tree as it stands. Prepended rather
# than appended so an installed distribution of the same name cannot shadow the
# thing under test -- which would turn this harness into the very fake it exists
# to avoid.
sys.path.insert(0, REPO)

from resources.lib.auth import device_code, errors, refresh, store  # noqa: E402
from resources.lib.auth.lock import RefreshLock  # noqa: E402

# The reference implementation's failure capture, reused rather than repeated,
# so a terminal failure seen through this harness is preserved the same way and
# under the same ignored filename pattern.
sys.path.insert(0, HERE)
from verify_device_code import capture_failure, report_capture  # noqa: E402

GRAPH_DEFAULT_DRIVE = 'https://graph.microsoft.com/v1.0/me/drive'
HTTP_TIMEOUT_SECONDS = 30

# Two, because one proves only that a refresh works. Three tokens observed in
# sequence is the smallest number that shows the SECOND rotation as well -- code
# that stored the first replacement and then re-sent it forever would pass a
# one-refresh check.
REFRESH_ROUNDS = 2

DEFAULT_SCRATCH = os.path.join(tempfile.gettempdir(),
                               'onedrive-kodi-live-scratch')

#: What `acquire` returns when --stop-after-code stopped it on purpose. A
#: sentinel rather than None, so a deliberate stop and a failed request cannot
#: be confused for one another -- they want opposite exit statuses, and a
#: harness that exits non-zero on success teaches its user to ignore the status.
STOPPED = object()


def banner(text):
    print('\n' + '=' * 68)
    print(text)
    print('=' * 68)


# ---------------------------------------------------------------------------
# The two things the auth package refuses to contain
# ---------------------------------------------------------------------------

def post(url, fields):
    """The HTTP port: post a form, return (status, parsed body).

    Same contract the Kodi transport implements, and the same one the tests'
    scripted endpoint implements -- which is what lets this drive the shipped
    modules unmodified.

    A 4xx carrying JSON is the protocol speaking, not a transport failure. RFC
    6749 section 5.2 defines every error response that way, and
    `authorization_pending` arrives as one for as long as the user is typing.
    """
    body = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(
        url, data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(request,
                                    timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {
                'error': device_code.NON_JSON_ERROR,
                'raw': raw[:400].decode(errors='replace'),
            }


def get_json(url, token):
    request = urllib.request.Request(
        url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(request,
                                    timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {'raw': raw[:400].decode(errors='replace')}


def sleep(seconds):
    """The abort-aware wait, with nothing to abort.

    In the add-on this is `Monitor.waitForAbort`, which returns True when Kodi
    is shutting down. Here nothing ever shuts down, so it always returns False
    -- and returning False rather than None matters, because `refresh` reads the
    result as "should I stop now".
    """
    time.sleep(seconds)
    return False


# ---------------------------------------------------------------------------
# Keeping real credentials out of the tree
# ---------------------------------------------------------------------------

def resolve_scratch(path):
    """An absolute scratch path, or SystemExit if it is somewhere it must not be.

    Two refusals, both of them cheap and both of them things a tired maintainer
    does at half past eleven:

      * inside this repository -- a real refresh token one `git add -A` away
        from being published in a GPL-licensed tree
      * a real Kodi profile -- this writes and then DELETES an account's token
        file, so pointing it at a live profile signs that account out
    """
    path = os.path.abspath(os.path.expanduser(path))

    try:
        inside_repo = (os.path.normcase(os.path.commonpath([path, REPO]))
                       == os.path.normcase(os.path.abspath(REPO)))
    except ValueError:
        inside_repo = False  # different drives on Windows; not inside
    if inside_repo:
        raise SystemExit(
            'refusing to write live tokens to %s: it is inside the repository.\n'
            'The ignore rules are a second line of defence, not the first one.'
            % path)

    lowered = path.replace('\\', '/').lower()
    for marker in ('/userdata/addon_data/', '/.kodi/', '/kodi/userdata/'):
        if marker in lowered:
            raise SystemExit(
                'refusing to write to %s: that looks like a real Kodi profile, '
                'and this harness deletes the account file it writes.' % path)
    return path


def describe_subject(subject):
    """The SHAPE of the subject claim, without publishing which person it is.

    `sub` is the account key: it names a filename on disk and it identifies a
    human. What is worth recording is that it is filename-safe and how long it
    is, which is what the store's validation cares about -- not its value.
    """
    if not subject:
        return 'absent'
    safe = store.SAFE_ACCOUNT_KEY.fullmatch(subject) is not None
    return ('%d characters, starts %s..., URL-safe base64: %s'
            % (len(subject), subject[:8], 'yes' if safe else 'NO'))


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def acquire(client_id, stop_after_code):
    """Sign in through the shipped protocol module. Returns the token response.

    The loop, the interval and the deadline live here on purpose: that is
    exactly the division `device_code.poll_once` was written for, and it is what
    puts the Kodi-side abort check in the Kodi-side loop. `poll_once` classifies
    one request and nothing more.
    """
    banner('STEP 1  Ask the shipped protocol module for a device code')
    print('  authority : %s' % device_code.AUTHORITY)
    print('  client_id : %s' % client_id)
    print('  scope     : %s' % device_code.SCOPES)

    response = device_code.request_device_code(post, client_id)

    if 'device_code' not in response:
        print('\nFAILED  the device-code request did not return a code')
        print(json.dumps(response, indent=2))
        report_capture(capture_failure(
            'harness-devicecode', '(request_device_code does not surface it)',
            response, device_code.AUTHORITY))
        failure = errors.classify_response(response)
        if failure is not None:
            print('\n  the shipped error table calls this: %r' % (failure,))
        return None

    print('\n  expires_in : %s seconds' % response.get('expires_in'))
    print('  interval   : %s seconds' % response.get('interval'))

    banner('STEP 2  Authorize on a phone')
    print('\n  Open:  %s' % response['verification_uri'])
    print('\n  Code:  %s\n' % response['user_code'])
    print('  Sign in with a WORK OR SCHOOL account.')
    print('  Read the consent screen -- what it lists is what a user sees.')

    if stop_after_code:
        print('\n  --stop-after-code: not polling. The code above will simply')
        print('  expire unused. The registration answered and the harness')
        print('  reached the grant; the grant itself is somebody else\'s turn.')
        return STOPPED

    interval = int(response.get('interval', device_code.DEFAULT_INTERVAL))
    deadline = time.time() + int(response.get('expires_in', 900))
    started = time.time()

    while True:
        if time.time() > deadline:
            print('\nFAILED  the code expired before it was entered')
            return None

        time.sleep(interval)

        try:
            state, payload = device_code.poll_once(
                post, client_id, response['device_code'])
        except device_code.TransportError as error:
            # Not a protocol answer at all. Says nothing about the grant, so it
            # is not fatal to the poll -- a captive portal or a proxy error page
            # lands here and the next tick may well succeed.
            print('  transport hiccup (%s); still polling' % error)
            continue

        if state == device_code.OK:
            print('\n  authorized after %ds' % int(time.time() - started))
            return payload

        if state == device_code.TERMINAL:
            print('\nFAILED  the grant was refused')
            print(json.dumps(payload, indent=2))
            report_capture(capture_failure(
                'harness-token-poll', '(poll_once returns state, not status)',
                payload, device_code.AUTHORITY))
            failure = errors.classify_response(payload)
            print('\n  the shipped error table calls this: %r' % (failure,))
            print('  Write that code into the runbook. A tenant that permits')
            print('  the grant cannot produce a refusal on demand, so whatever')
            print('  appeared here is the only one this project will observe.')
            return None

        interval = device_code.next_interval(interval, state)
        if state == device_code.SLOW_DOWN:
            print('  slow_down -> interval now %ds (permanently)' % interval)
        else:
            print('  waiting... (%ds)' % int(time.time() - started))


def report_token(token):
    """Everything about the first token that has to be recorded afterwards."""
    banner('STEP 3  What the provider actually granted')

    print('  token_type    : %s' % token.get('token_type'))
    print('  expires_in    : %s seconds' % token.get('expires_in'))
    print('  refresh_token : %s'
          % ('YES' if token.get('refresh_token')
             else 'NO -- offline_access did not survive'))
    print('  id_token      : %s' % ('yes' if token.get('id_token') else 'no'))
    print('\n  GRANTED SCOPE, verbatim -- record this string exactly, ordering')
    print('  included. It differs from the requested string in membership and')
    print('  in order, and it never contains offline_access even though a')
    print('  refresh token was issued:\n')
    print('    %s\n' % token.get('scope'))

    claims = device_code.read_identity_claims(token.get('id_token', ''))
    name = claims.get('name')
    print('  name claim    : %s'
          % ('PRESENT -- %r' % (name,) if name else 'ABSENT'))
    print('  subject claim : %s' % describe_subject(claims.get('sub')))
    print('  tenant claim  : %s' % ('present' if claims.get('tid') else 'absent'))

    if not name:
        print('\n  No name claim, so the label path falls through to the drive')
        print('  owner\'s display name. STEP 4 is what decides whether that')
        print('  fallback has anything to fall back to.')
    return claims


def report_drive_owner(access_token):
    """The fallback label, measured rather than assumed."""
    banner('STEP 4  The drive owner\'s display name (the label fallback)')

    status, body = get_json(GRAPH_DEFAULT_DRIVE, access_token)
    if status != 200:
        print('  FAIL %s  GET /me/drive' % status)
        print('  %s' % json.dumps(body)[:300])
        print('\n  The fallback has no source for this account. Record that.')
        return None

    owner = ((body.get('owner') or {}).get('user') or {})
    display_name = owner.get('displayName')
    print('  driveType          : %s' % body.get('driveType'))
    print('  owner.user.displayName : %s'
          % ('%r' % (display_name,) if display_name else 'NULL -- no fallback'))
    return display_name


def rotate(profile, account_key, client_id, first_token):
    """Write the blob through the store, then refresh twice through `refresh`.

    Every write here goes through `store.merge_token_response` and
    `store.write`, and every refresh through `refresh.refresh` holding a real
    `RefreshLock`. Nothing below reimplements any of it -- the whole value of
    this step is that the code being exercised is the code that ships.
    """
    banner('STEP 5  Write through the store, then rotate twice')

    store.accounts_dir(profile, create=True)
    token_file = store.token_path(profile, account_key)

    blob = store.merge_token_response({}, first_token)
    store.write(token_file, blob)
    print('  wrote the first blob to the scratch profile')
    print('  (%s, keyed on the subject claim)' % profile)

    prefixes = [refresh.fingerprint(blob.get('refresh_token'))]
    expiries = [blob.get('expires_in')]
    print('\n  refresh token #1 : %s   (expires_in %s)'
          % (prefixes[0], expiries[0]))

    lock = RefreshLock(store.lock_path(profile, account_key),
                       'live-harness-%d' % os.getpid(), sleep)

    for round_number in range(1, REFRESH_ROUNDS + 1):
        result = refresh.refresh(profile, account_key, lock, post, sleep,
                                 client_id=client_id, log=None)

        if result.outcome != refresh.SUCCEEDED:
            print('\n  refresh %d did not succeed: %s'
                  % (round_number, result.outcome))
            if result.failure is not None:
                print('  the shipped error table calls this: %r'
                      % (result.failure,))
            return prefixes, expiries, False

        prefixes.append(refresh.fingerprint(result.blob.get('refresh_token')))
        expiries.append(result.blob.get('expires_in'))
        print('  refresh token #%d : %s   (expires_in %s)%s'
              % (round_number + 1, prefixes[-1], expiries[-1],
                 '  [adopted]' if result.adopted else ''))

    return prefixes, expiries, True


def verdict(prefixes):
    """The stop condition, stated plainly."""
    banner('THE ROTATION')

    for index, prefix in enumerate(prefixes, start=1):
        print('  #%d  %s' % (index, prefix))

    if len(set(prefixes)) == len(prefixes):
        print('\n  PASS  all three differ. The provider rotates the refresh')
        print('        token, and the rotated value is reaching disk through')
        print('        the shipped store.')
        return True

    print('\n  FAIL  two of these match. The rotation is NOT reaching disk.')
    print('        Stop here. Every installation keeps working until the')
    print('        original token hits its ninety-day lifetime, and then they')
    print('        all fail on the same day with no code change to blame.')
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Sign in live through the add-on\'s own auth package.')
    parser.add_argument('--client-id', default=device_code.CLIENT_ID,
                        help='defaults to the identifier the add-on ships with')
    parser.add_argument('--scratch', default=DEFAULT_SCRATCH,
                        help='where the real token is written; must be outside '
                             'the repository and must not be a Kodi profile')
    parser.add_argument('--keep-tokens', action='store_true',
                        help='leave the live refresh token on disk afterwards')
    parser.add_argument('--stop-after-code', action='store_true',
                        help='ask for a device code and stop; does not sign in')
    args = parser.parse_args()

    profile = resolve_scratch(args.scratch)

    token = acquire(args.client_id, args.stop_after_code)
    if token is STOPPED:
        return 0
    if token is None:
        return 1

    claims = report_token(token)
    report_drive_owner(token['access_token'])

    subject = claims.get('sub')
    if not subject:
        print('\nFAILED  no subject claim, so there is no account key and')
        print('        nothing can be written through the store.')
        return 1

    account_key = store.validate_account_key(subject)
    prefixes, expiries, ok = rotate(profile, account_key, args.client_id, token)

    try:
        rotated = verdict(prefixes) if ok else False
        print('\n  expires_in, in order: %s' % (expiries,))
        print('  They are expected to DIFFER: the provider randomises the')
        print('  lifetime deliberately, so a constant anywhere would be wrong')
        print('  by measurement rather than by taste.')
    finally:
        if args.keep_tokens:
            print('\n  --keep-tokens: a live refresh token is still at %s'
                  % profile)
            print('  Delete it when you are done with it.')
        else:
            store.remove_account(profile, account_key)
            shutil.rmtree(profile, ignore_errors=True)
            print('\n  scratch profile removed; no live credential left behind')

    return 0 if (ok and rotated) else 1


if __name__ == '__main__':
    sys.exit(main())
