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
"""Fixtures for the behavioural tests of the packages that have no Kodi in them.

Nothing here imports a Kodi module, and nothing here opens a socket. Both are
deliberate: `resources/lib/auth/` and `resources/lib/graph/` are the parts of the
add-on that have no Kodi in them, so their tests need no stub library, and the
whole suite stays under two seconds. The same property is what
`tests/test_vendor_gates.py` states in its own docstring, and it is what makes
AUTH-13 testable at all.

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


# ---------------------------------------------------------------------------
# The recorded Graph responses, and the port that plays them back
# ---------------------------------------------------------------------------
#
# Resolved from this file's location and never from the working directory, for
# the same reason REPO_ROOT above is: the suite must give the same answer
# whichever directory it was started from.
GRAPH_FIXTURE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'fixtures', 'graph')

# The two kinds of drive the fixtures were captured from. This is a required
# argument everywhere below rather than a defaulted one, because the classes are
# not interchangeable: Microsoft's reserved-character list forbids '#' and '%' in
# a name on a Business drive outright, so a green Business run is not evidence
# about a Personal drive. A default would let one stand in for the other
# silently, which is the substitution CI-03's labelling rule exists to prevent
# and the reason SETUP-05 paid for two accounts.
DRIVE_CLASSES = ('business', 'personal')


class GraphTransportError(Exception):
    """No request was sent at all.

    The failure BROWSE-05 names is not an HTTP status: `http.client` refuses a
    request line carrying a disallowed character and raises before the socket is
    opened, so there is nothing to parse and nothing in a server log. The
    recorded envelope for that case carries `{"status": null,
    "transport_error": ...}` and no body, and this is what `FakeGraph` raises
    when it is asked to play one back.
    """


def load_graph_envelope(drive_class, name):
    """One recorded response, whole.

    The envelope, not the body. There are two shapes in this set -- an ordinary
    `{status, body}` and the bodiless `{status: null, transport_error}` above --
    and a loader that indexed `body` unconditionally could not express the
    second one, which is the single most important capture in the set.

    Every name, identifier, URL and paging token in these files is synthetic, as
    `tests/fixtures/graph/README.md` states. What is real is the *shape*: the
    keys, the nesting, the statuses, the presence or absence of a facet and the
    number of entries on a page. Assert against shape; a test that pins a value
    is pinning something the scrubber chose.
    """
    assert drive_class in DRIVE_CLASSES, (
        'the drive class must be given and must be one of %r; got %r. It is '
        'required rather than defaulted because a Business result standing in '
        'for a Personal one is a pass that proves nothing -- the two drives do '
        'not even allow the same characters in a name'
        % (DRIVE_CLASSES, drive_class))

    path = os.path.join(GRAPH_FIXTURE_ROOT, drive_class, name + '.json')
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def _graph_body(drive_class, name):
    """The response body of a recorded envelope, or a failure that names it."""
    envelope = load_graph_envelope(drive_class, name)
    assert 'body' in envelope, (
        'the %s fixture %r carries no body: it records a request that was never '
        'sent (%s), so there is no response to read. Ask it for the envelope '
        'instead' % (drive_class, name,
                     envelope.get('transport_error', 'no transport error '
                                                     'recorded')))
    return envelope['body']


class FakeGraph(object):
    """The Graph `get` port, scripted.

    Deliberately the same object as `FakeTokenEndpoint` above, in a different
    shape, and its four load-bearing properties are copied on purpose:

      * the script is positional and consumed in order with `pop(0)`;
      * every call is appended to `self.calls` **before** it is answered, so the
        call that fails is still on the record -- that is the extra request
        nobody intended and the one worth seeing;
      * running off the end raises rather than repeating the last answer, and
        the message counts calls against script length. A pager handed the last
        page twice looks like a listing that simply ended;
      * what was requested is readable afterwards, because the questions
        BROWSE-04 and BROWSE-17 ask are about what was *asked for*.

    The call signature is the port's own -- `get(path, **kwargs)` on the
    vendored provider, with `parameters` the kwarg every listing passes.

    A scripted answer may be a whole recorded envelope, in which case its body
    is returned and a bodiless one raises `GraphTransportError`; or a plain
    mapping, which is returned unchanged, so a test needing one synthetic page
    does not have to wrap it.
    """

    def __init__(self, *responses):
        self.queue = list(responses)
        self.scripted = len(responses)
        self.calls = []

    def __call__(self, path, parameters=None, **kwargs):
        self.calls.append((path,
                           None if parameters is None else dict(parameters)))
        if not self.queue:
            raise AssertionError(
                'the fake Graph port was called %d time(s) but only %d '
                'response(s) were scripted. The last answer is not repeated: a '
                'call the test did not intend is a defect to report, not one '
                'to absorb' % (len(self.calls), self.scripted))

        answer = self.queue.pop(0)
        if isinstance(answer, dict) and 'transport_error' in answer:
            raise GraphTransportError(
                '%s: no request was sent for %r' % (answer['transport_error'],
                                                    path))
        if isinstance(answer, dict) and 'body' in answer:
            return answer['body']
        return answer

    @property
    def paths(self):
        return [path for path, _parameters in self.calls]

    @property
    def last_parameters(self):
        return self.calls[-1][1]


@pytest.fixture
def graph_envelope():
    """Factory: graph_envelope(drive_class, name) -> the whole recorded envelope."""
    return load_graph_envelope


@pytest.fixture
def graph_body():
    """Factory: graph_body(drive_class, name) -> the recorded response body."""
    return _graph_body


@pytest.fixture
def fake_graph():
    """Factory: fake_graph(*responses) -> a scripted Graph `get` port."""
    def build(*scripted):
        return FakeGraph(*scripted)
    return build


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
