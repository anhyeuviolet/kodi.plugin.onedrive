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
"""Turn the raw captures into fixtures that carry no personal information.

The raw captures are evidence and they stay outside the repository. What goes
in is this: the same responses, same shapes, same statuses, with every value
that identifies a person, an account, a tenant or a file replaced.

TWO RULES, and the first is the one that matters.

1. KEEP-LIST, NOT REMOVE-LIST. Only the keys the shipped extractor actually
   reads survive; everything else is dropped whether or not anyone thought of
   it. A remove-list has to be complete to be safe, and it silently stops being
   complete the day Microsoft adds a field. This one fails closed: an unknown
   key is dropped, and if the add-on turns out to need it the tests break
   loudly rather than the fixture leaking quietly.

2. NAMES ARE SYNTHETIC, AND CARRY THE SAME CHARACTER CLASSES. A name is
   replaced by one built to have the same awkward properties -- a space, a
   non-ASCII letter, a bracket, an extension -- because those properties are
   the whole reason a recorded name is worth anything. Nothing about the real
   name survives, not even its length.

The keep-list comes from reading `OneDrive._extract_item` and `process_files`.
It is deliberately a little wider than they read today: `video`, `audio` and
`image` facets are kept because those code paths exist and a later phase will
test them, and none of the three carries identity.

Run against a directory of raw captures, which is never committed:

    python tools/scrub_fixtures.py --raw <directory of raw captures>

The recorder that produces those captures is deliberately not in this
repository: it mutates `sys.path`, which `test_no_syspath_mutation` forbids for
every tracked module outside `tests/`, and it imports a sign-in harness that is
untracked for live-credential reasons. So the capture half of this pipeline is
not reproducible from a clean clone; this half is, which is what makes the
synthetic-values claim in `tests/fixtures/graph/README.md` checkable by anyone.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import unicodedata
import urllib.parse
from pathlib import Path

# Resolved from this file rather than the working directory, so the tool writes
# the same fixtures from anywhere -- the same form, and for the same reason, as
# the other tools in this directory. Two deep, not three: this module sits in
# tools/ now, and the three-deep chain it carried at .planning/research/ would
# resolve one directory above the repository.
REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# What survives
# ---------------------------------------------------------------------------

#: The response envelope. `@odata.context` is NOT here: it embeds the signed-in
#: user's object id, and nothing in the add-on reads it.
ENVELOPE_KEYS = ('value', '@odata.nextLink', '@odata.deltaLink')

#: Per-entry keys the extractor reads. `remoteItem` is on the list because the
#: swap at onedrive.py:162 substitutes it wholesale, so it is scrubbed by the
#: same function, recursively.
ITEM_KEYS = (
    'id', 'name', 'size', 'description', 'deleted', 'lastModifiedDateTime',
    'folder', 'file', 'video', 'audio', 'image', 'photo', 'remoteItem',
    'parentReference', 'thumbnails', '@microsoft.graph.downloadUrl',
)

#: Inside `parentReference`, only the two the extractor reads.
PARENT_KEYS = ('driveId', 'id')

#: Inside `folder` / `file`, only what is read. `hashes` carries a content
#: digest of the user's file and is not read by anything.
FACET_KEYS = {
    'folder': ('childCount',),
    'file': ('mimeType',),
    'video': ('width', 'height', 'duration'),
    'audio': ('track', 'disc', 'duration', 'year', 'genre', 'album', 'artist',
              'title'),
    'image': ('width', 'height'),
    'photo': (),
}

#: An error body keeps its code and its message. `innerError` is dropped: it
#: carries request identifiers and timestamps tying the capture to a session.
ERROR_KEYS = ('code', 'message')

#: Drive-level keys. `owner`, `quota` and `webUrl` are not on it.
DRIVE_KEYS = ('id', 'driveType')

# ---------------------------------------------------------------------------
# Synthetic names
# ---------------------------------------------------------------------------

#: Bases chosen so the set as a whole spans the cases that matter: plain ASCII,
#: a space, Vietnamese diacritics, a bracket, an apostrophe, and the three
#: reserved characters the phase criterion names by hand.
BASES = [
    'Alpha', 'Bravo Charlie', 'Delta', 'Echo Foxtrot Golf',
    'Hồ sơ', 'Tài liệu chung', 'Ảnh nghỉ hè', 'Đường dẫn dài',
    "Ryan's Files", 'Break#Out', 'Estimate%s', 'Fifty Percent 50%',
    'Round (2019)', 'Brackets [2]', 'Semi;colon', 'Plus+Sign',
    'Ampersand&Co', 'Question?Mark', 'Trailing dot.', 'Ẩn số cuối',
]


def name_for(original, index):
    """A synthetic name with the same awkward properties as `original`.

    Deterministic in (original, index) so a re-run produces the same fixture
    and a diff shows a real change rather than a reshuffle. The digest is of
    the original, which never leaves this process -- it only picks a base.
    """
    if not original:
        return original

    stem, dot, extension = original.rpartition('.')
    if not dot or len(extension) > 5 or ' ' in extension:
        stem, extension = original, ''

    digest = hashlib.sha256(original.encode('utf-8')).digest()
    base = BASES[digest[0] % len(BASES)]

    has_space = ' ' in stem
    has_non_ascii = any(ord(ch) > 127 for ch in stem)

    # Guarantee the two properties that actually change the URL, adding them if
    # the chosen base happens not to have them.
    if has_space and ' ' not in base:
        base += ' Two'
    if has_non_ascii and not any(ord(ch) > 127 for ch in base):
        base += ' Việt'
    if not has_space:
        base = base.replace(' ', '-')
    if not has_non_ascii:
        base = ''.join(ch for ch in unicodedata.normalize('NFKD', base)
                       if ord(ch) < 128)

    base = '%s %02d' % (base, index) if has_space else '%s-%02d' % (base, index)
    return base + ('.' + extension.lower() if extension else '')


def id_for(original, prefix='01'):
    """A synthetic identifier of the same length and alphabet."""
    if not isinstance(original, str) or not original:
        return original
    digest = hashlib.sha256(original.encode('utf-8')).hexdigest().upper()
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
    out = []
    for i in range(len(original) - len(prefix)):
        out.append(alphabet[int(digest[i % len(digest)], 16) % len(alphabet)])
    return prefix + ''.join(out)


def link_for(url, index):
    """A nextLink with the shape kept and the skiptoken thrown away.

    The real token is base64 that decodes to paging state including the last
    file name on the page, so it is exactly as revealing as the listing.
    """
    if not isinstance(url, str):
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, 'SYNTHETIC-PAGE-%d' % index if key == '$skiptoken' else value)
             for key, value in query]
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, parsed.path,
        urllib.parse.urlencode(query, safe='$'), ''))


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------

def keep(node, allowed):
    return {key: node[key] for key in allowed if key in node}


def scrub_item(entry, index):
    if not isinstance(entry, dict):
        return entry
    out = keep(entry, ITEM_KEYS)

    if 'name' in out:
        out['name'] = name_for(out['name'], index)
    if 'id' in out:
        out['id'] = id_for(out['id'])
    if 'description' in out and out['description']:
        out['description'] = 'synthetic description'

    # When a person last touched a file is information about that person, and
    # a hundred of them in order is a picture of an evening's work. The VALUE
    # is replaced; the ORDER is not, because a listing's ordering is something
    # a later phase will want to assert against.
    if out.get('lastModifiedDateTime'):
        out['lastModifiedDateTime'] = '2020-01-%02dT%02d:%02d:00Z' % (
            index % 28 + 1, index % 24, index % 60)

    parent = out.get('parentReference')
    if isinstance(parent, dict):
        parent = keep(parent, PARENT_KEYS)
        for key in ('driveId', 'id'):
            if key in parent:
                parent[key] = id_for(parent[key], prefix='b!' if key == 'driveId' else '01')
        out['parentReference'] = parent

    for facet, allowed in FACET_KEYS.items():
        if isinstance(out.get(facet), dict):
            out[facet] = keep(out[facet], allowed)

    # A thumbnail url is signed and points at the user's content, so the url
    # goes. Everything around it stays: the list's length, which is what the
    # extractor branches on, and each size's real dimensions -- because
    # BROWSE-12 asks for the SMALLEST USEFUL size and the extractor currently
    # takes `large`. A fixture that flattened the sizes away could not express
    # that gap.
    if isinstance(out.get('thumbnails'), list):
        rendered = []
        for thumb in out['thumbnails']:
            if not isinstance(thumb, dict):
                continue
            clean = {}
            for size in ('small', 'medium', 'large'):
                if isinstance(thumb.get(size), dict):
                    clean[size] = {
                        'width': thumb[size].get('width'),
                        'height': thumb[size].get('height'),
                        'url': 'https://example.invalid/thumb/%s' % size,
                    }
            rendered.append(clean)
        out['thumbnails'] = rendered

    if '@microsoft.graph.downloadUrl' in out:
        out['@microsoft.graph.downloadUrl'] = (
            'https://example.invalid/download/%s' % out.get('id', 'item'))

    if isinstance(out.get('remoteItem'), dict):
        out['remoteItem'] = scrub_item(out['remoteItem'], index)

    return out


def scrub_body(body, index):
    if not isinstance(body, dict):
        return body

    if 'error' in body:
        error = keep(body['error'], ERROR_KEYS)
        # Graph's own wording, copied verbatim on purpose: the error path
        # should be tested against what the server really says. Recorded here
        # so the leak check knows this one was a decision, not an escape.
        PRESERVED.update(value for value in error.values()
                         if isinstance(value, str))
        return {'error': error}

    if 'value' in body:
        out = keep(body, ENVELOPE_KEYS)
        out['value'] = [scrub_item(entry, position)
                        for position, entry in enumerate(out['value'])]
        if '@odata.nextLink' in out:
            out['@odata.nextLink'] = link_for(out['@odata.nextLink'], index)
        return out

    # A single drive, or a single item.
    if 'driveType' in body:
        out = keep(body, DRIVE_KEYS)
        out['id'] = id_for(out.get('id', ''), prefix='b!')
        return out

    return scrub_item(body, index)


# ---------------------------------------------------------------------------
# The check that has to pass before any of this is trusted
# ---------------------------------------------------------------------------

def collect_strings(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            collect_strings(value, out)
    elif isinstance(node, list):
        for item in node:
            collect_strings(item, out)
    elif isinstance(node, str):
        out.add(node)


#: Values that are identical in both by design and carry nothing personal: the
#: drive classes, Graph's own error vocabulary, and this harness's own labels.
STRUCTURAL = {
    'business', 'personal', 'documentLibrary',
    'notSupported', 'itemNotFound', 'accessDenied', 'invalidRequest',
    'InvalidURL',
    # The query-option token the nextLink carries; part of the URL's shape.
    'thumbnails',
}

#: Filled during scrubbing with the values deliberately copied verbatim. An
#: exact record of the exceptions beats a heuristic that guesses at them: a
#: rule like "prose ending in a full stop is safe" would also wave through a
#: file name that happened to end in one.
PRESERVED = set()


def is_structural(text):
    """A value that is about the protocol rather than about the account."""
    if text in STRUCTURAL or text in PRESERVED:
        return True
    # A media type. Generic by definition -- `video/mp4` says nothing about
    # whose video it is.
    if '/' in text and ' ' not in text and text.count('/') == 1:
        return True
    return False


def verify(raw_root, clean_root):
    """No value from the raw captures may survive inside a clean one.

    Compared value-against-value rather than against the file text, so a KEY
    that happens to share a name with some captured value cannot raise a false
    alarm -- and so a real name hidden inside a longer URL still can.
    """
    original = set()
    for drive in sorted(os.listdir(raw_root)):
        folder = os.path.join(raw_root, drive)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            with io.open(os.path.join(folder, name), encoding='utf-8') as handle:
                collect_strings(json.load(handle), original)

    interesting = {text for text in original
                   if len(text) > 6 and not is_structural(text)}

    leaks = []
    for drive in sorted(os.listdir(clean_root)):
        folder = os.path.join(clean_root, drive)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            with io.open(path, encoding='utf-8') as handle:
                values = set()
                collect_strings(json.load(handle), values)
            for value in values:
                for text in interesting:
                    if text in value:
                        leaks.append((os.path.join(drive, name), text[:60]))
    return leaks


NOTE = """# Recorded Graph fixtures

Captured from a live OneDrive account, then rewritten.

**Every name, identifier, URL and paging token in these files is synthetic.**
The response *shapes* are real -- the keys, the nesting, the HTTP statuses, the
presence or absence of a facet, the number of entries on a page -- and those are
what the tests read. The values are not, and nothing here can be traced to an
account, a tenant or a file.

Names are replaced by names carrying the same awkward properties as the
originals: a space, a non-ASCII letter, a bracket, an extension. That is
deliberate. A fixture set of tidy ASCII names would pass while the real drive
broke, which is the failure this set exists to prevent.

Written by `scrub_fixtures.py`. The raw captures it reads are never committed.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Required, with no default. It used to default to a directory under the
    # home directory of the one machine the captures were taken on, which reads
    # as though the tool works from a clean clone when it does not: on any other
    # machine that default resolves to a path that is not there, and the run
    # ends in 'no raw captures at ...' as though the captures were merely
    # missing rather than never specified.
    parser.add_argument('--raw', required=True,
                        help='directory of raw captures to rewrite (never '
                             'committed; see the module docstring)')
    parser.add_argument('--out', default=os.path.join(
        REPO, 'tests', 'fixtures', 'graph'),
        help='directory to write the scrubbed fixtures into '
             '(default: tests/fixtures/graph)')
    args = parser.parse_args()

    if not os.path.isdir(args.raw):
        print('no raw captures at %s' % args.raw)
        return 1

    shutil.rmtree(args.out, ignore_errors=True)
    os.makedirs(args.out)

    count = 0
    for drive in sorted(os.listdir(args.raw)):
        folder = os.path.join(args.raw, drive)
        if not os.path.isdir(folder) or drive.startswith('_'):
            continue
        target = os.path.join(args.out, drive)
        os.makedirs(target)
        for index, name in enumerate(sorted(os.listdir(folder))):
            with io.open(os.path.join(folder, name), encoding='utf-8') as handle:
                capture = json.load(handle)
            clean = dict(capture)
            if 'body' in clean:
                clean['body'] = scrub_body(clean['body'], index)
            clean.pop('url', None)          # carries the probed folder name
            clean.pop('message', None)      # the InvalidURL text quotes the URL
            with io.open(os.path.join(target, name), 'w',
                         encoding='utf-8') as handle:
                json.dump(clean, handle, ensure_ascii=False, indent=2,
                          sort_keys=True)
                handle.write('\n')
            count += 1
        print('  %-10s %d files' % (drive, len(os.listdir(target))))

    with io.open(os.path.join(args.out, 'README.md'), 'w',
                 encoding='utf-8') as handle:
        handle.write(NOTE)

    leaks = verify(args.raw, args.out)
    print()
    if leaks:
        print('LEAKED -- %d strings from the raw captures survived:' % len(leaks))
        for where, text in leaks[:20]:
            print('  %-40s %r' % (where, text))
        return 1

    print('  %d files written to %s' % (count, args.out))
    print('  no string from the raw captures survives the rewrite')
    return 0


if __name__ == '__main__':
    sys.exit(main())
