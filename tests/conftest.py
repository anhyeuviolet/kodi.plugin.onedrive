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
"""Fixtures for the auth package's behavioural tests.

Nothing here imports a Kodi module, and nothing here opens a socket. Both are
deliberate: `resources/lib/auth/` is the part of the add-on that has no Kodi in
it, so its tests need no stub library, and the whole suite stays under two
seconds. The same property is what `tests/test_vendor_gates.py` states in its
own docstring, and it is what makes AUTH-13 testable at all.

The HTTP port is a plain callable -- `post(url, fields) -> (status, body)` --
that the auth package accepts by injection. `FakeTokenEndpoint` is that callable
with a scripted queue behind it, so a poll sequence reads as "pending, pending,
then success" at the call site.

Every token value here is synthetic. No credential from the live spike runs is
tracked in this repository (T-03-06).
"""

import base64
import json
import os
import sys

import pytest

# The repository root, so `import resources.lib.auth...` resolves however the
# suite was started. `python -m pytest` already puts the working directory on
# the path; a bare `pytest` does not, and a test file that only runs one of the
# two ways is a test file that stops being run. This lives in tests/, which the
# vendor gates exclude from the shipped-source sweeps -- the shipped tree still
# must never touch sys.path, because Kodi places the add-on root there itself.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# The measured device-code response, from SPIKE-DEVICE-CODE.md. Every field is
# the server's to supply: verification_uri really is login.microsoft.com/device
# and not the microsoft.com/devicelogin most documentation cites, and
# verification_uri_complete is absent, so a user code can never travel inside a
# URL or a QR code.
DEVICE_CODE_RESPONSE = {
    'device_code': 'synthetic-device-code',
    'user_code': 'K7QF3NBXZ',
    'verification_uri': 'https://login.microsoft.com/device',
    'expires_in': 900,
    'interval': 5,
    'message': 'To sign in, use a web browser to open the page ...',
}

# Both measured granted-scope strings. They differ from the requested scope and
# from each other in membership and in ordering, and neither contains
# offline_access even though every run issued a refresh token. Tests that touch
# a granted scope must use these, so an equality comparison cannot survive.
GRANTED_SCOPE_BUSINESS = 'openid profile email https://graph.microsoft.com/Files.Read'
GRANTED_SCOPE_PERSONAL = 'https://graph.microsoft.com/Files.Read openid profile'


def _b64url(raw):
    """URL-safe base64 with the padding stripped, exactly as a JWT carries it.

    The stripping matters: it is what forces the decoder to re-pad, and a
    decoder that is only ever handed padded input never exercises that branch.
    """
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


class FakeTokenEndpoint(object):
    """The HTTP port, scripted.

    Call signature is the port's: (url, fields) -> (status, body), with body
    already parsed. Responses are consumed in the order they were given, and
    running off the end of the script fails loudly rather than repeating the
    last answer -- a poll loop that polls one more time than the test intended
    is a bug the test should report, not absorb.
    """

    def __init__(self, *responses):
        self.queue = list(responses)
        self.calls = []

    def __call__(self, url, fields):
        self.calls.append((url, dict(fields)))
        if not self.queue:
            raise AssertionError(
                'the fake token endpoint was called %d time(s) but only %d '
                'response(s) were scripted' % (len(self.calls),
                                               len(self.calls) - 1))
        return self.queue.pop(0)

    @property
    def urls(self):
        return [url for url, _fields in self.calls]

    @property
    def last_fields(self):
        return self.calls[-1][1]


class ResponseFactory(object):
    """Builders for each answer the token endpoint can give.

    The status codes are the measured ones: a protocol state such as
    authorization_pending arrives as HTTP 400 with a JSON body, which is the
    whole of AUTH-10 and the reason these builders exist rather than a literal
    per test.
    """

    device_code_response = DEVICE_CODE_RESPONSE
    granted_scope_business = GRANTED_SCOPE_BUSINESS
    granted_scope_personal = GRANTED_SCOPE_PERSONAL

    def device_code(self, **overrides):
        answer = dict(DEVICE_CODE_RESPONSE)
        answer.update(overrides)
        return 200, answer

    def pending(self):
        return 400, {
            'error': 'authorization_pending',
            'error_description': 'AADSTS70016: OAuth 2.0 device flow error. '
                                 'Authorization is pending.',
        }

    def slow_down(self):
        return 400, {
            'error': 'slow_down',
            'error_description': 'AADSTS70016: polling too frequently.',
        }

    def terminal(self, code='expired_token', description=None):
        return 400, {
            'error': code,
            'error_description': description or ('AADSTS70019: %s' % code),
        }

    def token(self, **overrides):
        """A successful token exchange.

        expires_in is one of the three values the spike measured (3655, 4491,
        3599) rather than 3600, so a test that assumed the round number fails.
        """
        answer = {
            'token_type': 'Bearer',
            'scope': GRANTED_SCOPE_PERSONAL,
            'expires_in': 3655,
            'access_token': 'synthetic-access-token-1',
            'refresh_token': 'synthetic-refresh-token-1',
            'id_token': self.id_token(),
        }
        answer.update(overrides)
        return 200, answer

    def refresh(self, **overrides):
        """A refresh response. Carries no id_token; Entra does not resend one."""
        answer = {
            'token_type': 'Bearer',
            'scope': GRANTED_SCOPE_PERSONAL,
            'expires_in': 4491,
            'access_token': 'synthetic-access-token-2',
            'refresh_token': 'synthetic-refresh-token-2',
        }
        answer.update(overrides)
        return 200, answer

    def id_token(self, **claims):
        """A compact-serialization id_token whose payload carries `claims`.

        The signature segment is a fixed string: nothing in the add-on verifies
        it, by design (D-01), so a test that produced a real one would be
        asserting a property the code deliberately does not have.
        """
        payload = {
            'name': 'Nguyen Tien Dat',
            'preferred_username': 'synthetic@example.invalid',
            'sub': 'synthetic-subject-key',
            'tid': '9188040d-6c67-4c5b-b112-36a304b66dad',
        }
        payload.update(claims)
        return '.'.join((
            _b64url(json.dumps({'alg': 'RS256', 'typ': 'JWT'}).encode('utf-8')),
            _b64url(json.dumps(payload).encode('utf-8')),
            'not-a-real-signature',
        ))


@pytest.fixture
def responses():
    return ResponseFactory()


@pytest.fixture
def fake_endpoint():
    """Factory: fake_endpoint(*responses) -> a scripted HTTP port."""
    def build(*scripted):
        return FakeTokenEndpoint(*scripted)
    return build


@pytest.fixture
def store_dir(tmp_path):
    """The per-account directory the token store writes into.

    A real directory on a real filesystem, because the properties under test --
    the sibling temp file, the exclusive create, the replace -- are filesystem
    properties and a mocked one would assert nothing.
    """
    path = tmp_path / 'addon_data' / 'accounts'
    path.mkdir(parents=True)
    return path


@pytest.fixture
def store_path(store_dir):
    """One account's token file, keyed by the identity token's `sub` claim."""
    return store_dir / 'synthetic-subject-key.json'
