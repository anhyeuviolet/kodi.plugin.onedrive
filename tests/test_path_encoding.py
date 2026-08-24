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
"""What happens to a real folder name on the way into a Graph address.

The measurement this file exists for. `get_folder_items` concatenated the user's
path into the URL untouched, and a folder whose name contains a space therefore
produced **no request at all**: `http.client` refuses to put a disallowed
character on the request line, its guard is
`_contains_disallowed_url_pchar_re = [\\x00- \\x7f]`, and a space is `\\x20` --
inside that range. The listing failed before the network was involved, so there
was no status code to read and nothing in a server log to find.

The character that stops the request is the space, not the accented letter. This
matters for how the assertions are built: `Việt` encodes to non-ASCII UTF-8
bytes and would be rejected too, but a test written around the accented letter
would be exercising a path most drives never take, while the space is in
half the folder names on a real drive. So the space is what the end-to-end
assertion turns on, and the letter rides along in the same name to keep the
UTF-8 rule visible.

Why a table of literals rather than the recorded fixtures. The fixtures carry
the *character classes* -- a name with a space, one with a bracket, one with a
non-ASCII letter -- and later plans read them. ROADMAP success criterion 2 names
three exact strings by hand, and a criterion written as text is checked against
text: `ENCODING_CASES` below carries those three rows verbatim.
"""

import pytest

from kodistub import kodi_stubs
from resources.lib.graph import paths


# Each row is (segment, expected). The first three are ROADMAP success criterion
# 2 word for word; the rest are the character classes the recorded fixtures
# carry, so the table and the fixture set cover the same ground.
ENCODING_CASES = [
    ("Ryan's Files", "Ryan's%20Files"),
    ('Break#Out', 'Break%23Out'),
    ('estimate%s.docx', 'estimate%25s.docx'),
    ('Việt', 'Vi%E1%BB%87t'),
    ('Question?Mark-15.msi', 'Question%3FMark-15.msi'),
    # "+" is a sub-delim and survives. It is worth a row because the other
    # standard-library encoder, `quote_plus`, would turn a space into "+" here,
    # and a name that already contains one would then be indistinguishable from
    # a name that contained a space.
    ('Plus+Sign-01', 'Plus+Sign-01'),
    pytest.param(
        'Brackets [2] 07', 'Brackets%20%5B2%5D%2007',
        # "[" and "]" are outside `pchar`, so RFC 3986 requires encoding them --
        # and Microsoft's own addressing page nonetheless shows
        # `saved_game[1].bin` unencoded in a worked example. This expectation
        # deliberately disagrees with that example. Encoding a character that
        # need not be encoded is safe; failing to encode one that must be is
        # not, and only one of those two mistakes can lose a user's folder.
        id='brackets-encoded-against-microsofts-published-example'),
]


@pytest.mark.parametrize('segment,expected', ENCODING_CASES)
def test_a_segment_is_percent_encoded_for_the_url(segment, expected):
    encoded = paths.encode_segment(segment)

    assert encoded == expected, (
        'the folder name %r encodes to %r, not the required %r. What this costs '
        'on a device is the whole listing: a name carrying a character the '
        'request line disallows produces no request, so the user sees an empty '
        'folder and the log shows no HTTP status at all'
        % (segment, encoded, expected))


def test_the_default_safe_set_would_fail_the_criterion_as_written():
    """The explicit safe set is load-bearing, not decorative.

    `quote` with its default safe set turns the apostrophe into %27, and Graph
    resolves that form perfectly well -- so this is not a bug that would break a
    device. It is a mismatch with the criterion's own text, which names
    `Ryan's%20Files`. Recording it here is what stops the next reader deleting
    `safe=PCHAR_SAFE` as redundant and quietly failing a criterion nothing else
    checks.

    Naming the default call directly is allowed here because this file is under
    `tests/`, which the shipped-source sweeps exclude.
    """
    from urllib.parse import quote

    assert quote("Ryan's Files") == 'Ryan%27s%20Files', (
        'the standard library no longer produces the form this test exists to '
        'contrast with; the argument for writing PCHAR_SAFE out by hand has to '
        'be re-made rather than assumed')
    assert paths.encode_segment("Ryan's Files") == "Ryan's%20Files", (
        "the encoder now agrees with the default safe set, which means "
        "PCHAR_SAFE has stopped being applied; ROADMAP criterion 2 names "
        "Ryan's%20Files by hand and %27 is not that string")


PATH_CASES = [
    # The criterion's own two awkward names, in one path.
    ("/Ryan's Files/estimate%s.docx", "/Ryan's%20Files/estimate%25s.docx"),
    # A path made only of separators produces only separators.
    ('/', '/'),
    ('', ''),
    (None, ''),
    # Two adjacent separators never collapse into one: '/a//b' and '/a/b' are
    # different addresses, and an encoder that repairs the first into the second
    # is guessing at what the caller meant.
    ('/a//b', '/a//b'),
    # Segments are mapped independently, so input order survives exactly.
    ('/b/a', '/b/a'),
]


@pytest.mark.parametrize('path,expected', PATH_CASES)
def test_a_path_is_encoded_one_segment_at_a_time(path, expected):
    encoded = paths.encode_path(path)

    assert encoded == expected, (
        'the path %r encodes to %r, not %r' % (path, encoded, expected))


def test_a_separator_inside_a_segment_is_data_not_a_boundary():
    """`encode_segment` knows nothing about separators.

    A "/" that arrives inside one segment is a character in a name. Letting it
    through would let a name introduce a path segment of its own, which is the
    tampering T-02-01 names.
    """
    assert paths.encode_segment('a/b') == 'a%2Fb', (
        'a "/" inside a single segment survived as a separator, so a name '
        'chosen by somebody else can add a path segment to an address this '
        'add-on builds')


def test_a_folder_name_with_a_space_reaches_a_request(tmp_path):
    """End to end: what `get_folder_items` actually asks Graph for.

    This is the assertion the rest of the file supports. The encoder can be
    correct in isolation while the provider never calls it, and that failure is
    invisible to every table above.

    The recorder is two lines and deliberately not the shared scripted port:
    what is being asserted is the *argument* of one call, not a sequence of
    answers. The scripted `FakeGraph` in `tests/conftest.py` is for the pager
    and search tests, which need a sequence; this recorder is permanent, not
    scaffolding waiting to be replaced.
    """
    with kodi_stubs(tmp_path / 'profile'):
        # Inside the `with` body, never at module scope. `_Restore.check`
        # removes every `resources.*` module imported while the stubs were
        # installed and then asserts the removal; a module-scope import here
        # would be performed before the stubs existed, would fail without Kodi,
        # and if it somehow succeeded would leave a module with a fake `xbmc`
        # bound in its globals for every later test in the session.
        from resources.lib.provider.onedrive import OneDrive

        requested = []

        def record(path, **kwargs):
            requested.append(path)
            return {'value': []}

        provider = OneDrive()
        provider._driveid = 'synthetic-drive-id'
        provider.get = record

        provider.get_folder_items(path='/Round (2019) Việt')

    assert len(requested) == 1, (
        'get_folder_items made %d request(s), not 1: %r' % (len(requested),
                                                            requested))
    asked = requested[0]

    assert 'Round%20(2019)%20Vi%E1%BB%87t' in asked, (
        'the request path is %r, which does not carry the encoded folder name. '
        'The provider is not reaching the encoder, so this listing fails on a '
        'device before any request is sent' % (asked,))
    assert ' ' not in asked, (
        'the request path %r still contains a raw space. http.client refuses '
        'the request line outright, so the user gets an empty folder and there '
        'is no HTTP status anywhere to explain it' % (asked,))


def test_the_recorded_capture_shows_no_request_was_ever_sent(graph_envelope):
    """The evidence BROWSE-05 rests on, read out of the capture rather than
    described.

    `children_by_path_unencoded` is what the recorder got when it asked for a
    folder whose name contains a space, with the path concatenated in raw: no
    status and no body, because `http.client` raised `InvalidURL` before
    anything left the machine. Every other fixture in the set carries a status,
    so this one is the whole reason the loader returns the envelope rather than
    the body.
    """
    envelope = graph_envelope('business', 'children_by_path_unencoded')

    assert envelope['status'] is None, (
        'the capture records status %r. If a status was received then a request '
        'was sent, and the failure this test describes is a different one'
        % (envelope['status'],))
    assert 'body' not in envelope, (
        'the capture carries a body: %r. A request that was never sent has no '
        'response to have parsed' % (envelope,))
    assert envelope['transport_error'] == 'InvalidURL', (
        'the capture records %r rather than the InvalidURL http.client raises '
        'on a request line carrying a disallowed character'
        % (envelope['transport_error'],))
