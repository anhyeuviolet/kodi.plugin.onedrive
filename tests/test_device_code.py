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
"""The device authorization grant, driven end to end without Kodi and without
a socket.

The protocol itself is not in question here: SPIKE-DEVICE-CODE.md ran it three
times against this project's own registration on two account classes. What these
tests hold in place is the shape the add-on carries -- that a 400 is the protocol
speaking, that the continue set is an allow-list, and that the identity token is
read for display only.
"""

import pytest

from resources.lib.auth import device_code, store


def test_end_to_end_pending_then_token_is_merged_written_and_read_back(
        fake_endpoint, responses, store_path):
    """The tracer: one device code, one pending poll, one token, on disk.

    This is the whole vertical slice the rest of the phase expands sideways
    from. If it passes, the shape is right; every later plan adds cases to it
    rather than changing it.
    """
    post = fake_endpoint(
        responses.device_code(),
        responses.pending(),
        responses.token(),
    )

    granted = device_code.request_device_code(post, device_code.CLIENT_ID)

    # Read from the response, never from a literal: the server returns
    # login.microsoft.com/device, not the URL most documentation cites.
    assert granted['verification_uri'] == 'https://login.microsoft.com/device'
    assert granted['user_code']
    assert 'verification_uri_complete' not in granted

    state, payload = device_code.poll_once(
        post, device_code.CLIENT_ID, granted['device_code'])
    assert state == device_code.PENDING
    assert payload['error'] == 'authorization_pending'

    state, payload = device_code.poll_once(
        post, device_code.CLIENT_ID, granted['device_code'])
    assert state == device_code.OK
    assert payload['access_token'] == 'synthetic-access-token-1'

    blob = store.merge_token_response({}, payload)
    store.write(str(store_path), blob)

    assert store.read(str(store_path)) == blob


def test_written_blob_carries_the_five_fields_the_readers_need(
        fake_endpoint, responses, store_path):
    """access_token, refresh_token, expires_in and date are what the existing
    OAuth2._validate_access_tokens requires; issued_at is the new field the
    startup keepalive reads."""
    post = fake_endpoint(responses.token())
    _state, payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    store.write(str(store_path), store.merge_token_response({}, payload))
    blob = store.read(str(store_path))

    for key in ('access_token', 'refresh_token', 'expires_in', 'date',
                'issued_at'):
        assert key in blob, 'the written blob is missing %r' % key

    # The measured value, not the round number. Entra randomises the lifetime;
    # the spike observed 3655, 4491 and 3599 across three runs.
    assert blob['expires_in'] == 3655


def test_pending_arrives_as_http_400_and_is_read_as_protocol(
        fake_endpoint, responses):
    """AUTH-10. A 400 with a parseable body is the protocol speaking, and must
    not be reachable by the exception path."""
    status, _body = responses.pending()
    assert status == 400, 'the fixture must present pending as a 400 or this ' \
                          'test proves nothing'

    post = fake_endpoint(responses.pending())
    state, _payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    assert state == device_code.PENDING


def test_slow_down_is_classified_apart_from_pending(fake_endpoint, responses):
    """Both continue the loop, but only one changes the interval, so they
    cannot share a classification."""
    post = fake_endpoint(responses.slow_down())
    state, _payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    assert state == device_code.SLOW_DOWN
    assert state != device_code.PENDING


def test_a_documented_error_is_terminal(fake_endpoint, responses):
    post = fake_endpoint(responses.terminal('expired_token'))
    state, payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    assert state == device_code.TERMINAL
    assert payload['error'] == 'expired_token'


def test_continue_set_has_exactly_two_members(responses):
    """AUTH-09. An allow-list, and small enough to read at a glance."""
    assert device_code.CONTINUE_ON == frozenset(
        ('authorization_pending', 'slow_down'))


def test_an_error_code_that_exists_in_no_reference_is_terminal(fake_endpoint,
                                                               responses):
    """AUTH-09, and the assertion that makes the allow-list an allow-list
    rather than a stop-list with extra steps.

    Microsoft returns codes that appear in neither RFC 8628 nor the Entra
    documentation. Under a stop-list every one of them continues the loop, so
    the add-on polls a live endpoint forever on a failure it will never
    recover from.
    """
    invented = 'AADSTS_this_code_exists_in_no_reference'
    assert invented not in device_code.CONTINUE_ON

    post = fake_endpoint(responses.terminal(invented))
    state, payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    assert state == device_code.TERMINAL
    assert payload['error'] == invented


def test_an_empty_error_code_is_terminal(fake_endpoint, responses):
    """A 400 with no error field at all is still not one of the two."""
    post = fake_endpoint((400, {'error_description': 'something went wrong'}))
    state, _payload = device_code.poll_once(post, device_code.CLIENT_ID, 'dc')

    assert state == device_code.TERMINAL


def test_slow_down_raises_the_interval_by_five(responses):
    assert device_code.next_interval(5, device_code.SLOW_DOWN) == 10


def test_a_pending_poll_leaves_the_interval_alone(responses):
    assert device_code.next_interval(5, device_code.PENDING) == 5
    assert device_code.next_interval(10, device_code.PENDING) == 10


def test_the_slow_down_increase_is_permanent(fake_endpoint, responses):
    """RFC 8628 section 3.5: the interval is increased by five seconds "for
    this and all subsequent requests". The permanence is the whole point -- a
    per-poll recomputation from the server's original interval would undo it on
    the very next tick and the endpoint would throttle the add-on again."""
    post = fake_endpoint(
        responses.pending(),
        responses.slow_down(),
        responses.pending(),
        responses.pending(),
    )

    interval = device_code.DEFAULT_INTERVAL
    seen = []
    for _ in range(4):
        state, _payload = device_code.poll_once(
            post, device_code.CLIENT_ID, 'dc')
        interval = device_code.next_interval(interval, state)
        seen.append(interval)

    assert seen == [5, 10, 10, 10], \
        'the interval came back down after the slow_down: %s' % seen


def test_a_400_that_will_not_parse_is_a_transport_failure(fake_endpoint):
    """The protocol answers in JSON. A body that is not JSON did not come from
    the protocol -- it is a captive portal, a proxy error page or a truncated
    response -- and it must surface as a transport failure rather than as a
    terminal protocol error.

    The distinction is not cosmetic: a terminal protocol error means the grant
    is dead and the account needs re-authorising, while a transport failure
    means the network is having a moment. Collapsing the two signs the user out
    because their Wi-Fi dropped.
    """
    post = fake_endpoint((400, {
        'error': device_code.NON_JSON_ERROR,
        'raw': '<html><title>502 Bad Gateway</title>',
    }))

    with pytest.raises(device_code.TransportError):
        device_code.poll_once(post, device_code.CLIENT_ID, 'dc')


def test_a_transport_failure_is_not_in_the_continue_set():
    """It must not loop either. Raising is what makes that unambiguous."""
    assert device_code.NON_JSON_ERROR not in device_code.CONTINUE_ON


def test_scope_string_is_the_locked_set():
    """AUTH-04, D-01. Exact, because this is the requested scope -- the string
    the add-on sends. The granted string that comes back is a different
    question and is never compared for equality."""
    assert device_code.SCOPES == (
        'https://graph.microsoft.com/Files.Read offline_access openid profile')


def test_requested_scope_by_membership():
    """AUTH-04, by membership on a split rather than on the whole string, so
    the assertion says which permission it objects to."""
    requested = device_code.SCOPES.split()

    assert set(requested) == {
        'https://graph.microsoft.com/Files.Read',
        'offline_access',
        'openid',
        'profile',
    }


def test_no_write_broad_or_application_wide_grant_is_requested():
    """The consent screen the user reads on a TV is the whole of what they can
    judge. Anything here that is not read-only on files is a promise the add-on
    made and cannot keep."""
    for forbidden in ('.default', '.All', 'ReadWrite', '.Write', 'Sites.',
                      'Directory.', 'Mail.', 'User.Read.All'):
        assert forbidden not in device_code.SCOPES, \
            '%r is in the requested scope' % forbidden


def test_a_granted_scope_is_only_ever_tested_by_membership(responses):
    """Both strings here were measured, one per account class. They differ in
    membership -- Entra adds `email` for work/school without being asked -- and
    in ordering, and neither contains `offline_access` even though every run
    issued a refresh token. Any equality or prefix check on a granted scope is
    a bug waiting for the other account class."""
    business = responses.granted_scope_business
    personal = responses.granted_scope_personal

    assert business != personal
    assert not business.startswith(personal)
    assert not personal.startswith(business)

    # What is actually true of both, and the only shape of check that is.
    for granted in (business, personal):
        parts = set(granted.split())
        assert 'https://graph.microsoft.com/Files.Read' in parts
        assert 'offline_access' not in parts, \
            'the absence of offline_access from the granted scope is normal ' \
            'and must never be read as a failure to get a refresh token'


def test_one_authority_serves_both_account_classes():
    """D-01. The spike proved /common serves work/school and personal alike
    across three live runs, so there is no authority branch and no user-facing
    authority setting to get wrong."""
    assert device_code.AUTHORITY == (
        'https://login.microsoftonline.com/common/oauth2/v2.0')
    assert device_code.DEVICE_CODE_ENDPOINT == device_code.AUTHORITY + '/devicecode'
    assert device_code.TOKEN_ENDPOINT == device_code.AUTHORITY + '/token'


def test_request_device_code_posts_the_client_id_and_the_scope(
        fake_endpoint, responses):
    post = fake_endpoint(responses.device_code())
    device_code.request_device_code(post, device_code.CLIENT_ID)

    url, fields = post.calls[0]
    assert url == device_code.DEVICE_CODE_ENDPOINT
    assert fields['client_id'] == device_code.CLIENT_ID
    assert fields['scope'] == device_code.SCOPES


def test_poll_posts_the_device_code_grant(fake_endpoint, responses):
    post = fake_endpoint(responses.pending())
    device_code.poll_once(post, device_code.CLIENT_ID, 'synthetic-device-code')

    url, fields = post.calls[0]
    assert url == device_code.TOKEN_ENDPOINT
    assert fields['grant_type'] == (
        'urn:ietf:params:oauth:grant-type:device_code')
    assert fields['client_id'] == device_code.CLIENT_ID
    assert fields['device_code'] == 'synthetic-device-code'


def test_identity_claims_are_decoded_for_display_and_keying(responses):
    """AUTH-21. `name` is the label the account list shows and `sub` is the key
    the per-account files are named by. Nothing else is taken from them."""
    claims = device_code.read_identity_claims(
        responses.id_token(name='Ada Lovelace', sub='stable-account-key'))

    assert claims['name'] == 'Ada Lovelace'
    assert claims['sub'] == 'stable-account-key'


def test_identity_claims_survive_an_unpadded_payload(responses):
    """A JWT strips base64 padding. A decoder that does not re-pad raises on
    two payloads in three, which reads as 'sign-in works on some accounts'."""
    seen = set()
    for i in range(6):
        token = responses.id_token(name='n' * i, sub='s' * i)
        payload_segment = token.split('.')[1]
        seen.add(len(payload_segment) % 4)
        assert device_code.read_identity_claims(token)['sub'] == 's' * i

    assert len(seen) > 1, 'every payload happened to be the same length mod ' \
                          '4; this test never exercised the padding branch'


def test_unreadable_identity_token_yields_no_claims():
    """An empty dictionary, never an exception: a missing display name must not
    take down a sign-in that otherwise succeeded."""
    for bad in ('', 'not-a-jwt', 'a.b', 'a.!!!!.c', None):
        assert device_code.read_identity_claims(bad) == {}


def test_nothing_in_the_auth_package_imports_kodi():
    """CI-01. The property that lets this whole file run with no stub library."""
    import ast
    import glob
    import os

    package = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'resources', 'lib', 'auth')
    sources = sorted(glob.glob(os.path.join(package, '*.py')))
    assert sources, 'the auth package has no sources; this sweep would pass ' \
                    'vacuously'

    offenders = []
    for path in sources:
        with open(path, 'r', encoding='utf-8') as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or '']
            for name in names:
                if name.split('.')[0].startswith('xbmc'):
                    offenders.append('%s:%d: %s' % (path, node.lineno, name))

    assert not offenders, 'the auth package must import no Kodi module:\n' + \
                          '\n'.join(offenders)


def test_the_fake_endpoint_leaks_no_real_credential():
    """T-03-06. Read this file's own fixture source rather than trusting it."""
    import os

    conftest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'conftest.py')
    with open(conftest, 'r', encoding='utf-8') as handle:
        text = handle.read()

    # A real Entra access token is a JWT beginning 'eyJ' and runs to well over
    # a thousand characters. Nothing of that shape belongs in a tracked file.
    assert 'eyJ' not in text
    for line in text.splitlines():
        assert len(line) < 200, 'a suspiciously long literal is in the ' \
                                'fixtures: ' + line[:80]

    # And the values that are there say what they are.
    assert 'synthetic-access-token-1' in text
