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
