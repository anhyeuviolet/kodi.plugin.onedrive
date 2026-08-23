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
"""The contract between a provider token response and the vendored OAuth2 layer.

The rest of the suite tests `resources/lib/auth/` on one side and reads the
vendored tree statically on the other. Nothing tested the join, and the join is
where the sign-in broke on hardware: `resources/lib/auth/` produces a *blob*,
the vendored `OAuth2` consumes a *blob*, and a provider `response` is not one.
It carries `expires_in` and no `date`, and `date` is stamped locally by
`store.merge_token_response`. `OAuth2._validate_access_tokens` requires it and
`OAuth2.prepare_request` computes expiry from `date + expires_in - 600`.

These are behavioural, not static. They import the real vendored module and
call the real validator, which is possible without a Kodi stub library because
every `xbmc*` import in the vendored tree is function-local -- `Logger` and
`KodiUtils` both import inside their methods. Nothing here reaches one.
"""

import time

import pytest

from resources.lib.auth import store
from resources.lib.vendor.clouddrive_common.exception import RequestException
from resources.lib.vendor.clouddrive_common.remote.oauth2 import OAuth2


class _Probe(OAuth2):
    """The smallest thing that is an OAuth2.

    `prepare_request` is what the sign-in flow actually reaches -- through
    `provider.get_account` -- so it is what these tests drive, rather than
    calling the private validator and asserting about a method the flow never
    touches directly.
    """

    API_URL = 'https://graph.microsoft.com/v1.0'

    def __init__(self):
        self.persisted = []
        self.refreshed = 0

    def _get_api_url(self):
        return self.API_URL

    def _get_request_headers(self):
        return {}

    def get_access_tokens(self):
        """Nothing stored, which is what the store returns before a sign-in."""
        return {}

    def refresh_access_tokens(self, request_params=None):
        self.refreshed += 1
        raise AssertionError(
            'prepare_request tried to refresh. The blob under test was just '
            'issued, so a refresh here means its expiry was read as already '
            'past -- which is what a missing or zeroed `date` looks like.')

    def persist_access_tokens(self, access_tokens):
        self.persisted.append(access_tokens)


@pytest.fixture
def token_response(responses):
    """The provider's own answer to a successful device-code exchange."""
    _status, body = responses.token()
    return body


def test_the_provider_sends_no_date(token_response):
    """The premise, asserted rather than assumed.

    If Entra ever started sending `date` this whole class of defect would be
    impossible and the merge at the sign-in seam would be redundant. It does
    not: the measured responses in SPIKE-DEVICE-CODE.md carry `expires_in` and
    `ext_expires_in` and no absolute time at all.
    """
    assert 'expires_in' in token_response
    assert 'date' not in token_response


def test_a_raw_token_response_is_rejected_by_the_oauth2_layer(token_response):
    """The defect, at the size of one call.

    This is the exact failure the television showed: sign-in succeeded, the
    response was passed on as it arrived, and the first request made with it
    raised before it reached the network.
    """
    probe = _Probe()
    with pytest.raises(RequestException):
        probe.prepare_request('get', '/me', access_tokens=dict(token_response))


def test_the_merged_response_is_accepted_by_the_oauth2_layer(token_response):
    blob = store.merge_token_response({}, token_response)

    probe = _Probe()
    request = probe.prepare_request('get', '/me', access_tokens=blob)

    assert probe.refreshed == 0
    assert request.headers['authorization'] == (
        'Bearer ' + token_response['access_token'])


def test_the_merge_supplies_exactly_what_was_missing(token_response):
    """Named field by field, so a rename in either half fails here.

    `store` and `OAuth2` are on opposite sides of the vendor boundary and
    neither names the other. The four field names are the whole of the
    agreement between them.
    """
    blob = store.merge_token_response({}, token_response)
    for field in ('access_token', 'refresh_token', 'expires_in', 'date'):
        assert field in blob, (
            '%r is missing from a merged blob. OAuth2._validate_access_tokens '
            'requires all four, and the one that is easy to lose is `date`, '
            'because it is the only one the provider does not send.' % field)


def test_the_stamped_expiry_is_not_already_past(token_response):
    """`date` is not decoration; it is the origin of the expiry arithmetic.

    A blob carrying `date = 0` would satisfy the validator and then be treated
    as expired on the spot, so every first request after a sign-in would spend
    the refresh token it had just been given.
    """
    blob = store.merge_token_response({}, token_response)
    assert blob['date'] + blob['expires_in'] - 600 > time.time()


# ---------------------------------------------------------------------------
# What that rejection is allowed to say
# ---------------------------------------------------------------------------
#
# The rejection above reached a Kodi dialog on a television, and what it put on
# screen was the token blob rendered whole -- token_type, scope, expires_in and
# then the access token itself. CloudDriveAddon._handle_exception renders a
# UIException's root exception as line 2 of the dialog, and _identify wraps
# every failure of provider.get_account in one, so this message is a
# user-visible string by construction rather than by accident.
#
# The same raise embedded the request data, which for a token exchange is a
# form body carrying the refresh token, the device code and the client id.
#
# These drive the real message. The gate in tests/test_auth_gates.py stops the
# construct coming back anywhere in shipped source; these say what the message
# has to be instead.

def _rejection(probe, **kwargs):
    """The RequestException prepare_request raises for an invalid blob."""
    with pytest.raises(RequestException) as caught:
        probe.prepare_request('post', '/token', **kwargs)
    return caught.value


def test_the_rejection_does_not_print_the_token(token_response):
    error = _rejection(_Probe(), access_tokens=dict(token_response))

    message = str(error)
    for field in ('access_token', 'refresh_token', 'id_token'):
        value = token_response.get(field)
        if not value:
            continue
        assert value not in message, (
            'the rejection prints the %s. This message is rendered into a Kodi '
            'dialog by _handle_exception and written to the Kodi log, which '
            'users paste into forum posts verbatim -- and for a live blob the '
            'token IS the credential, there is nothing else to steal.' % field)


def test_the_rejection_names_the_missing_field_and_the_ones_present(token_response):
    error = _rejection(_Probe(), access_tokens=dict(token_response))

    message = str(error)
    assert 'date' in message, (
        'the rejection does not say which required field is missing. `date` is '
        'the answer nine times out of ten -- it means a response reached the '
        'OAuth2 layer without going through store.merge_token_response -- and '
        'a maintainer who is not told it cannot act on this message at all')
    for name in ('token_type', 'scope', 'expires_in'):
        assert name in message, (
            'the rejection does not say that %r arrived. Field names are not '
            'credentials, and knowing which ones turned up is what separates '
            'an unmerged response from an empty blob from a truncated one'
            % name)


def test_an_empty_blob_says_so_rather_than_printing_a_brace():
    error = _rejection(_Probe(), access_tokens=None)
    assert 'no token blob at all' in str(error)


def test_the_rejection_redacts_the_request_data():
    """The third argument, which _handle_exception appends to the log report."""
    error = _rejection(_Probe(), access_tokens={'access_token': 'a'},
                       parameters={
                           'grant_type': 'refresh_token',
                           'refresh_token': 'synthetic-refresh-token-long-enough',
                           'client_id': 'synthetic-client-id',
                       })

    report = str(error.request)
    assert 'synthetic-refresh-token-long-enough' not in report, (
        'the rejection embeds the request body unredacted. A token exchange '
        'sends the refresh token in that body:\n%s' % report)
    assert 'refresh_token=' in report, (
        'the request data is not reported at all. Redaction means cutting the '
        'value short, not dropping the field: which field was sent is the '
        'diagnostically useful half\n%s' % report)


def test_a_short_credential_in_the_request_data_goes_entirely():
    """03-08's rule, reached through this path.

    Keeping a fixed prefix of a nine-character user code is not a fingerprint,
    it is the code with a typo, and it is live for as long as the dialog is on
    screen. A value shorter than twice the prefix is dropped whole.
    """
    error = _rejection(_Probe(), access_tokens={'access_token': 'a'},
                       parameters={'device_code': 'K7QF3NBXZ'})

    report = str(error.request)
    assert 'K7QF3NBXZ' not in report
    assert 'K7QF3NB' not in report, (
        'a short credential was half-masked rather than removed:\n%s' % report)


def test_the_rejection_redacts_the_bearer_header():
    error = _rejection(_Probe(), access_tokens={'access_token': 'a'},
                       headers={'content-type': 'application/json',
                                'authorization': 'Bearer synthetic-access-token-1'})

    report = str(error.request)
    assert 'synthetic-access-token-1' not in report, (
        'the rejection reports the authorization header in the clear:\n%s'
        % report)
    assert 'content-type' in report, (
        'no header reached the report at all, so this assertion certifies '
        'nothing:\n%s' % report)


def test_the_rejection_survives_a_report_it_cannot_render():
    """Reporting is not allowed to be the thing that fails.

    prepare_request calls the validator a second time with the plain strings
    'refresh_access_tokens' and 'Unknown' in place of a URL and headers.
    Iterating that string as a mapping would report a dictionary of single
    characters; raising over it would lose the original failure entirely.
    """
    probe = _Probe()
    with pytest.raises(RequestException) as caught:
        probe._validate_access_tokens({}, 'refresh_access_tokens', 'Unknown',
                                      'Unknown')
    assert 'Unknown' in str(caught.value.request)
