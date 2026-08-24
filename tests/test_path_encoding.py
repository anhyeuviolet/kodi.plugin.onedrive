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

The OData half of the file, and what it does not claim. BROWSE-06 -- "a search
query containing a single quote succeeds" -- is Phase 4's requirement and is not
claimed here. What lands here is the rule ROADMAP criterion 2 names by hand,
written once so that both places that build an OData string literal reach it,
and Phase 4 inherits it rather than deriving it a third time. Quote-doubling and
percent-encoding answer to different specifications -- OData v4.01 section 2.2
and RFC 3986 -- and they are applied in that order, because the literal is a
layer below the URL.
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


# ---------------------------------------------------------------------------
# The OData string literal (ROADMAP criterion 2, second half)
# ---------------------------------------------------------------------------

# Each row is (text, expected literal). Doubling only; the percent-encoding is
# the layer above and has its own table below.
ODATA_CASES = [
    ("O'Neil", "O''Neil"),
    ('plain', 'plain'),
    ('', ''),
]


@pytest.mark.parametrize('text,expected', ODATA_CASES)
def test_a_single_quote_is_doubled_inside_an_odata_literal(text, expected):
    doubled = paths.odata_literal(text)

    assert doubled == expected, (
        'the query %r becomes the literal %r, not %r. An undoubled quote closes '
        "the literal early, and everything after it is read by the service as "
        'expression rather than as text' % (text, doubled, expected))


ODATA_QUOTED_CASES = [
    # Both apostrophes survive the encoder untouched, because "'" is a sub-delim
    # and is in the pchar safe set.
    ("O'Neil", "O''Neil"),
    # The space and the "#" are the URL layer's problem; the apostrophe is the
    # literal layer's. One call answers both.
    ("it's a #1 file", "it''s%20a%20%231%20file"),
]


@pytest.mark.parametrize('text,expected', ODATA_QUOTED_CASES)
def test_a_query_is_doubled_and_then_percent_encoded(text, expected):
    quoted = paths.odata_quoted(text)

    assert quoted == expected, (
        'the query %r goes into the URL as %r, not %r' % (text, quoted,
                                                          expected))


def test_the_rule_is_doubling_first_and_percent_encoding_second():
    """The order is part of the rule, not an implementation detail.

    Encoding first and doubling second would produce a URL Graph accepts too --
    but only by a coincidence of *this* encoder, which leaves "'" alone because
    it is a sub-delim. The moment the safe set stops including it, the reversed
    order silently stops doubling anything at all: there is no literal quote
    left to double, only a `%27` the service will decode back into one after the
    doubling step has already run.

    That is why the rule is about the literal and belongs below the URL layer.
    The composition is asserted through the two exported names, and then the
    reversal is shown failing against an encoder that does encode the quote --
    which is the only way to make the difference visible at all.
    """
    from urllib.parse import quote

    name = "O'Neil"

    assert paths.odata_quoted(name) == paths.encode_segment(
        paths.odata_literal(name)), (
        'odata_quoted is no longer the encoder applied to the doubled literal, '
        'so the two exported names and the one call sites use have drifted '
        'apart')

    assert quote(paths.odata_literal(name)) == 'O%27%27Neil', (
        'doubling first survives an encoder that encodes the quote: the service '
        'decodes %27%27 back into a doubled quote, which is still one literal '
        "apostrophe")
    assert paths.odata_literal(quote(name)) == 'O%27Neil', (
        'the reversed order is expected to lose the doubling entirely against '
        'such an encoder; if it no longer does, the argument for fixing the '
        'order has to be re-made rather than assumed')


# The output the shipped `get_subtitles` produced before this refactor, for a
# name carrying an apostrophe. It already doubled by hand, so what changes is
# only how many characters of the doubled literal survive as themselves: the
# service decodes both spellings to the same OData literal, which is what the
# assertion below compares.
TODAYS_SUBTITLE_QUERY = 'O%27%27Neil'


def test_the_subtitle_search_asks_the_service_for_the_same_literal(tmp_path):
    """A refactor of `get_subtitles`, not a fix to it.

    This call site already doubled by hand; the change is that it stops carrying
    its own copy of the rule. The OData literal the service parses must be
    identical to what it received before, and it is -- `%27%27` and `''` decode
    to the same two characters. Comparing the decoded forms is what says that,
    where comparing the raw strings would report a difference that does not
    exist anywhere the query is actually read.
    """
    from urllib.parse import unquote

    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive

        requested = []

        def record(path, **kwargs):
            requested.append(path)
            return {'value': []}

        provider = OneDrive()
        provider._driveid = 'synthetic-drive-id'
        provider.get = record

        provider.get_subtitles('synthetic-parent-id', "O'Neil.mkv")

    assert len(requested) == 1, (
        'get_subtitles made %d request(s), not 1: %r' % (len(requested),
                                                        requested))
    asked = requested[0]

    assert "search(q='O''Neil')" in asked, (
        'the subtitle search asks for %r, which does not carry the doubled '
        'literal. An undoubled quote here means the search for a subtitle '
        'beside a file whose name contains an apostrophe returns nothing, and '
        'the video plays without subtitles for a reason nothing reports'
        % (asked,))
    assert unquote(asked).endswith(unquote(TODAYS_SUBTITLE_QUERY) + "')"), (
        'the literal this call site sends has changed from %r. This was meant '
        'to be a refactor: the doubling rule moved, the request did not'
        % (TODAYS_SUBTITLE_QUERY,))


def test_a_search_query_with_an_apostrophe_no_longer_closes_the_literal(tmp_path):
    """The call site that never doubled at all.

    `search` went straight to the percent-encoder, which emits a single `%27`;
    the service decodes it back into a quote, and that quote ends the literal.
    Everything the user typed after it is then read as expression. This is the
    tampering T-02-02 names, and it is the half of the rule that is a fix rather
    than a refactor.
    """
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive

        requested = []

        def record(path, **kwargs):
            requested.append(path)
            return {'value': []}

        provider = OneDrive()
        provider._driveid = 'synthetic-drive-id'
        provider.get = record

        provider.search("O'Neil")

    asked = requested[0]

    assert "search(q='O''Neil')" in asked, (
        'the search asks for %r. The quote the user typed is not doubled, so '
        'the service reads the rest of what they typed as an expression rather '
        'than as the text they were searching for' % (asked,))
