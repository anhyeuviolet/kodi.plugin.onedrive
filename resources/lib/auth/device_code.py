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
"""The OAuth 2.0 device authorization grant (RFC 8628), for the Microsoft
identity platform.

Nothing in this module imports a Kodi module, and nothing in it opens a socket.
The HTTP port is a callable the caller supplies:

    post(url, fields) -> (status, body)

where `body` is already-parsed JSON. That is the whole coupling to the network,
and it is what lets the entire protocol be tested without a stub library.

The protocol itself is settled: `.planning/research/SPIKE-DEVICE-CODE.md` ran
this flow three times against this project's own registration, on a work/school
account and on a personal one. The constants below are the measured ones.
"""

import base64
import json

# One authority for both account classes. The spike proved /common serves
# work/school and personal accounts alike across three live runs, so there is no
# authority branch here and no user-facing authority setting to get wrong.
AUTHORITY = 'https://login.microsoftonline.com/common/oauth2/v2.0'
DEVICE_CODE_ENDPOINT = AUTHORITY + '/devicecode'
TOKEN_ENDPOINT = AUTHORITY + '/token'

# The add-on's own public client. A device-code client is public by definition:
# it holds no secret, and embedding this identifier is what the grant type is
# for. AUTH-19 will let an installation override it with its own registration.
CLIENT_ID = 'efe197b3-5c14-4d67-810f-e10406742a06'

# AUTH-04 locks this exactly. Read-only on files, plus the offline grant that
# yields a refresh token, plus the two that yield an id_token for labelling.
# Note that the *granted* scope that comes back differs from this string in both
# membership and ordering between account classes, and never contains
# offline_access even though a refresh token is always issued -- so a granted
# scope may only ever be tested by membership, never by equality or prefix.
SCOPES = 'https://graph.microsoft.com/Files.Read offline_access openid profile'

# RFC 8628: keep polling on these and only these. This is an allow-list on
# purpose. Microsoft returns error codes that appear in no reference, and a
# stop-list -- "continue unless the error is one of these known-fatal ones" --
# turns the first such code into an infinite loop against a live endpoint.
# Adding a member here is a decision to poll forever on that code.
CONTINUE_ON = frozenset(('authorization_pending', 'slow_down'))

# What one poll can mean. Exactly four outcomes, so a caller cannot forget one.
OK = 'ok'
PENDING = 'authorization_pending'
SLOW_DOWN = 'slow_down'
TERMINAL = 'terminal'

# RFC 8628 section 3.4: wait at least `interval` seconds, or 5 if the server did
# not say. The spike measured 5 in every run; this is the floor, not a guess.
DEFAULT_INTERVAL = 5

# RFC 8628 section 3.5: a slow_down raises the interval by five seconds "for
# this and all subsequent requests". The permanence is the part that matters.
SLOW_DOWN_INCREMENT = 5


def request_device_code(post, client_id=CLIENT_ID):
    """Ask for a device code. Returns the parsed response as the server gave it.

    Everything the sign-in dialog needs -- `user_code`, `verification_uri`,
    `expires_in`, `interval` -- comes out of this dictionary and must never come
    from a literal. The server returns `https://login.microsoft.com/device`,
    which is not the `microsoft.com/devicelogin` most documentation cites, and
    it omits `verification_uri_complete` entirely, so a user code can never
    travel inside the URL or inside a QR code.
    """
    _status, body = post(DEVICE_CODE_ENDPOINT, {
        'client_id': client_id,
        'scope': SCOPES,
    })
    return body


def poll_once(post, client_id, device_code):
    """Exchange the device code once. Returns (state, payload).

    `state` is one of OK, PENDING, SLOW_DOWN or TERMINAL, and `payload` is the
    parsed body in every case -- the token on OK, the error object otherwise.

    The caller owns the loop, the interval and the deadline. This function
    performs one request and classifies it, which is what makes it testable
    against a scripted endpoint and what keeps the Kodi-side abort check in the
    Kodi-side loop where it belongs.

    A 400 carrying a parseable JSON body is the protocol speaking, not a
    transport failure: RFC 6749 section 5.2 defines every error response that
    way, and `authorization_pending` -- the ordinary state for as long as the
    user is typing the code into their phone -- arrives as one. That
    classification is the whole of AUTH-10.
    """
    _status, body = post(TOKEN_ENDPOINT, {
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
        'client_id': client_id,
        'device_code': device_code,
    })

    if body.get('access_token'):
        return OK, body

    error = body.get('error', '')
    if error not in CONTINUE_ON:
        # Everything that is not in the two-member allow-list stops the loop,
        # including codes this add-on has never seen. AUTH-18 turns the code
        # into a sentence; the job here is only to stop.
        return TERMINAL, body

    if error == 'slow_down':
        return SLOW_DOWN, body
    return PENDING, body


def read_identity_claims(id_token):
    """Decode an id_token's payload. Returns {} on anything unreadable.

    No signature is checked here and none should be. Trust in these claims comes
    from having received them over TLS directly from the token endpoint, and
    they are used for two things only: `name` labels the account in the list,
    and `sub` keys that account's files on disk (D-01, AUTH-21).

    No authorization decision may be taken from this dictionary. Treating a
    decoded claim as an authorization fact is exactly how a display convenience
    becomes a vulnerability, and the caller has an access token for anything
    that is actually an authorization question.

    Returning {} rather than raising is deliberate: a sign-in that succeeded
    must not be undone because the display name could not be read.
    """
    try:
        payload = id_token.split('.')[1]
        # A JWT strips base64 padding. Put it back, or two payloads in three
        # fail to decode -- which would read as "sign-in works on some accounts".
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
    except Exception:
        return {}
    if not isinstance(claims, dict):
        return {}
    return claims
