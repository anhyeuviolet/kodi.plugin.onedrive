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
"""How a user's own text is written into a Graph address: one path segment at a
time, and one OData string literal at a time.

Nothing here imports a Kodi module, and nothing here opens a socket. That is the
point of the package rather than a coincidence of the file: `resources/lib/graph/`
is the part of the add-on whose rules can be run and asserted on a development
host with no Kodi installed, so a test of them needs no stub library and no
device. Every import below is the standard library, and nothing under
`resources.lib.` is imported at all.

The two rules are separate on purpose, because they answer to different
specifications. Percent-encoding answers to RFC 3986, which is about what a URL
may contain. Quote-doubling answers to OData v4.01 section 2.2, which is about
what a string literal may contain -- a layer *below* the URL, and applied first.
"""

from urllib.parse import quote


# RFC 3986: pchar = unreserved / pct-encoded / sub-delims / ":" / "@". What has
# to be named here is only the tail of that production, because `quote` never
# encodes `unreserved` (ALPHA / DIGIT / "-" / "." / "_" / "~") in any case. So
# this string is sub-delims + ":" + "@", written out rather than inherited.
#
# ":" is in the safe set even though the delimiters a path gets wrapped in --
# `root:` and `:/children` -- are built out of it. That is safe because
# OneDrive's own reserved-character list forbids ":" inside an item name
# outright, so a segment arriving here can never carry one and can never close
# those delimiters early.
#
# "/" is deliberately absent. It is the separator `encode_path` splits on, and a
# "/" that somehow arrives *inside* one segment is data: it must come back as
# %2F rather than introduce a path segment nobody asked for (T-02-01).
PCHAR_SAFE = "!$&'()*+,;=:@"


def encode_segment(segment):
    """One path segment, percent-encoded for a Graph URL.

    Knows nothing about separators. A "/" handed to this function is a character
    in a name, not a boundary, and comes back as %2F.

    `None` becomes the empty string rather than raising. A missing name and an
    empty one address the same thing here -- the parent -- and a listing that
    fails with a TypeError deep inside URL construction tells the user nothing.
    """
    if segment is None:
        return ''
    return quote(segment, safe=PCHAR_SAFE)


def encode_path(path):
    """A whole path, encoded one segment at a time.

    Split on "/", map `encode_segment` over the parts, rejoin on "/". The single
    call `quote(path, safe='/' + PCHAR_SAFE)` would produce the same bytes for
    every input this add-on can construct, and it is still not what is written
    here, for two reasons. The requirement is worded about segments, so code
    shaped like the requirement can be checked against it by reading. And an
    empty segment stays visible: '/a//b' keeps its empty middle part instead of
    being quietly repaired into '/a/b', which is a different address.

    `None` and the empty string both return the empty string, so a caller that
    has no path at all gets one it can concatenate rather than an exception.
    """
    if not path:
        return ''
    return '/'.join(encode_segment(part) for part in path.split('/'))


def odata_literal(text):
    """The body of an OData single-quoted string literal.

    OData v4.01 section 2.2: a single quote inside such a literal is written
    twice. An undoubled one closes the literal, and everything the user typed
    after it is read by the service as expression rather than as text -- which
    is a query that fails, and, given a query somebody else chose, a query that
    was rewritten (T-02-02).

    Text only. Nothing here knows it is going into a URL; that is the next
    function's job, and keeping the two apart is what stops the order being
    swapped by accident.
    """
    if not text:
        return ''
    return text.replace("'", "''")


def odata_quoted(text):
    """A search term, ready to sit between the quotes of `search(q='...')`.

    Doubling first, percent-encoding second, and the order is the rule rather
    than a detail. Reversed, the encoder would turn the user's quote into `%27`,
    the doubling step would then find no quote to double, and the service would
    decode `%27` back into the single quote that closes the literal -- the
    original defect, arriving one step later.

    With the safe set this module uses the two orders happen to agree, because
    an apostrophe is a sub-delim and `encode_segment` leaves it alone. That
    agreement is a property of the safe set, not of the rule, so it is not
    something to depend on.
    """
    return encode_segment(odata_literal(text))
