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
"""Repository gates for the vendor lift.

Every assertion here is over the repository as text, XML or AST. Nothing in this
file imports a Kodi module, so it needs no stub library and no fixtures, and the
whole file runs in well under two seconds.

Failures report path and line number, never a bare count: a count cannot be acted
on. Every sweep carries an explicit non-vacuity guard, because a sweep that passes
because it found nothing certifies nothing.
"""

import ast
import compileall
import functools
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

# The repository root, the index-backed file lists, the one exclusion set, the
# pattern sweep and the failure report all live in gatelib, because this is no
# longer the only gate file. Two copies of the exclusion set drift; one does not.
from gatelib import (
    REPO,
    excluded as _excluded,
    python_sources,
    read as _read,
    report as _report,
    source_scan,
    text_files,
    tracked_files,
)

# Not every shipped file is GPL. The vendored QR encoder is BSD-3-Clause with
# an MIT PNG writer bundled inside it, and stamping a GPL banner on either
# would be exactly the re-attribution the last assertion in
# test_gpl_headers_intact forbids. These files are therefore held to their own
# upstream notice rather than excused from carrying one: each entry names one
# exact string that must appear, so adding a row here is a stricter demand and
# never an escape hatch. Like the exclusion sets above, this lives here and
# nowhere else.
FOREIGN_NOTICES = {
    'resources/lib/vendor/pyqrcode/__init__.py': 'Michael Nooner',
    'resources/lib/vendor/pyqrcode/builder.py': 'Michael Nooner',
    'resources/lib/vendor/pyqrcode/tables.py': 'Michael Nooner',
    'resources/lib/vendor/pyqrcode/png.py': 'Johann C. Rocholl',
}

# Pinned at plan time from the file as it stands. Do not recompute and re-pin:
# re-pinning after an accidental edit is exactly the failure this catches.
LICENSE_SHA256 = '0b383d5a63da644f628d99c33976ea6487ed89aaa59f0b3257992deac1171e6b'

# This repository's own URL legitimately embeds the upstream-derived repository
# name. It is one of the two places the bare add-on id literal is correct.
OWN_REPO_URL = 'https://github.com/anhyeuviolet/kodi.plugin.onedrive'

# The other. GitHub Pages derives the site path from the git repository name, so
# the published repository's URLs carry that same name whether anyone wants them
# to or not - renaming the git repository is the only way to change it, and that
# would break the URL already declared to every installed copy.
#
# It is exempt on exactly the grounds OWN_REPO_URL is: the literal here names a
# *location*, not an add-on id, and nothing resolves it through
# xbmcaddon.Addon(id). Subtracted as an exact string rather than by loosening the
# pattern, so the sweep still catches `plugin.onedrive` one character either side
# of this URL, and so widening the exemption is a visible edit to this line.
OWN_PAGES_URL = 'https://anhyeuviolet.github.io/kodi.plugin.onedrive'

# The dotted path the module lives at after the lift.
VENDORED_PREFIX = 'resources.lib.vendor.clouddrive_common'


# ---------------------------------------------------------------------------
# The one list that stays here: it exists for the compile check below and has
# no second reader, so moving it to the shared harness would buy nothing.
# ---------------------------------------------------------------------------

def addon_tree_python():
    """Every tracked .py under resources/, plus the two root entry scripts."""
    files = [rel for rel in tracked_files()
             if rel.startswith('resources/') and rel.endswith('.py')]
    files.extend(rel for rel in ('entrypoint.py', 'service.py')
                 if rel in tracked_files())
    return files


# ---------------------------------------------------------------------------
# Licence and attribution (ID-03)
# ---------------------------------------------------------------------------

def test_license_unmodified():
    copies = [rel for rel in tracked_files()
              if PurePosixPath(rel).name == 'LICENSE.txt']
    assert copies == ['LICENSE.txt'], (
        'exactly one LICENSE.txt must be tracked, at the repository root; the '
        'upstream copy is byte-identical and is not vendored a second time. '
        'Found: %r' % (copies,))

    digest = hashlib.sha256((REPO / 'LICENSE.txt').read_bytes()).hexdigest()
    assert digest == LICENSE_SHA256, (
        'LICENSE.txt has changed: %s != pinned %s. A reflow, a re-encoding or a '
        'reordering fails here rather than passing as equivalent. Restore the '
        'file; do not re-pin the digest.' % (digest, LICENSE_SHA256))


def test_gpl_headers_intact():
    py = python_sources()
    assert py, 'no tracked Python source found - the gate would pass vacuously'

    exempt = [rel for rel in py if (REPO / rel).stat().st_size == 0]
    not_markers = [rel for rel in exempt
                   if PurePosixPath(rel).name != '__init__.py']
    assert not not_markers, (
        'only zero-byte __init__.py package markers are exempt from the '
        'copyright header; these are empty and are not markers:\n' +
        '\n'.join(not_markers))

    checked = [rel for rel in py if rel not in set(exempt)]
    assert 'entrypoint.py' in checked, (
        'entrypoint.py must be in the checked set, otherwise this sweep can '
        'pass without having read a single real source file')

    # A row in FOREIGN_NOTICES that names nothing in the tree means the map has
    # drifted, which is how a per-file expectation quietly stops checking a file.
    orphans = sorted(set(FOREIGN_NOTICES) - set(checked))
    assert not orphans, (
        'FOREIGN_NOTICES names files that are not checked source:\n' +
        '\n'.join(orphans))

    missing = []
    for rel in checked:
        head = '\n'.join(_read(rel).splitlines()[:25])
        expected = FOREIGN_NOTICES.get(rel, 'GNU General Public License')
        if expected not in head:
            missing.append('%s (expected %r)' % (rel, expected))
    assert not missing, (
        'these files lost their copyright notice from the first 25 lines; the '
        'expected phrase is the one for that file\'s own licence:\n' +
        '\n'.join(missing))

    attributed = [rel for rel in checked if 'Carlos Guzman' in _read(rel)]
    assert attributed, (
        'no checked source file names Carlos Guzman; the upstream copyright '
        'notice must be preserved, not re-attributed')


# ---------------------------------------------------------------------------
# Identity and rename completeness (ID-01, VND-02, VND-04)
# ---------------------------------------------------------------------------

def test_addon_id_everywhere():
    # Negative lookahead: grep -E cannot express this, re can.
    pattern = re.compile(r'plugin\.onedrive(?!\.kn)')
    exempt = (OWN_REPO_URL, OWN_PAGES_URL)

    def subtract(line):
        for url in exempt:
            line = line.replace(url, '')
        return line

    hits = source_scan(pattern, transform=subtract)
    assert not hits, (
        'the bare add-on id survives outside %s:\n%s'
        % (' and '.join(exempt), _report(hits)))


def test_both_url_exemptions_are_load_bearing():
    """Each exempt URL must contain the forbidden literal and must still be in use.

    An exemption that names a string no *swept* file contains has stopped doing
    work, and it sits beside one that has not - the same drift `EXCLUDED_DOCS`
    suffers and the same reason `FOREIGN_NOTICES` is checked for orphans. The
    carrier must be a file the sweep actually reads, so this cannot be satisfied
    by the copy of the literal in this gate file: `tests/` is excluded, and a
    test that certified itself would certify nothing.
    """
    pattern = re.compile(r'plugin\.onedrive(?!\.kn)')
    for url in (OWN_REPO_URL, OWN_PAGES_URL):
        # What is exempt is a *location*. Shortening an entry towards the bare
        # literal - to `plugin.onedrive`, say - would subtract the forbidden
        # string from every line in the tree and switch the sweep off entirely
        # while leaving it green, which is the one failure mode an exemption
        # list has. Only an absolute https URL can name a location.
        assert url.startswith('https://') and len(url) > len('https://') + 8, (
            '%r is not an absolute https URL; only a location may be exempt, '
            'and an entry shortened towards the bare add-on id disables the '
            'sweep for every line in the tree' % (url,))
        assert pattern.search(url), (
            '%r is in the exemption list but does not contain the literal the '
            'sweep forbids, so subtracting it accomplishes nothing' % (url,))
        carriers = [rel for rel, contents in text_files()
                    if url in contents and not _excluded(rel)]
        assert carriers, (
            'no file this sweep reads contains %r; the exemption is dead and '
            'must be deleted rather than left to widen the sweep for whatever '
            'line is written next' % (url,))


def test_no_legacy_package_prefix():
    # Remove the new dotted path first, so the assertion reads "no reference
    # outside the vendored path" rather than "no reference at all".
    pattern = re.compile(r'clouddrive\.common')
    hits = source_scan(pattern, transform=lambda line: line.replace(VENDORED_PREFIX, ''))
    assert not hits, (
        'the legacy package prefix is referenced outside %s:\n%s'
        % (VENDORED_PREFIX, _report(hits)))


def test_no_hardcoded_module_id():
    pattern = re.compile(r'script\.module\.clouddrive\.common')
    hits = source_scan(pattern)
    assert not hits, (
        'the upstream add-on id literal survives; every one of these resolves '
        'through xbmcaddon.Addon(id) and raises "Unknown addon id" on a clean '
        'profile:\n' + _report(hits))


def test_no_unanchored_rename_damage():
    # The two corruption shapes an unanchored substring replacement produces.
    # Both still parse and still run; they fail only at add-on lookup time on a
    # clean profile. A grep for the original literal cannot see either.
    shapes = [r'script\.module\.[A-Za-z0-9_.]*vendor', r'script\.module\.resources']
    damage = []
    for shape in shapes:
        damage.extend(source_scan(re.compile(shape)))
    assert not damage, (
        'an unanchored rename rewrote an add-on-id literal into nonsense:\n' +
        _report(damage))


def test_no_syspath_mutation():
    hits = [h for h in source_scan(re.compile(r'sys\.path\.(append|insert)'))
            if h[0].endswith('.py')]
    assert not hits, (
        'Kodi already places the add-on root on sys.path; mutating it is a '
        'shadowing bug waiting for a machine with a sibling add-on '
        'installed:\n' + _report(hits))


def test_vendor_tree_self_contained():
    allowed_roots = set(sys.stdlib_module_names) | {'resources'}
    visited = 0
    offenders = []
    relative_import_files = set()

    for rel in addon_tree_python():
        tree = ast.parse(_read(rel), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                relative_import_files.add(rel)
                visited += 1
                continue
            if isinstance(node, ast.Import):
                visited += 1
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                visited += 1
                names = [node.module or '']
            else:
                continue
            for name in names:
                root = name.split('.')[0]
                if root in allowed_roots or root.startswith('xbmc'):
                    continue
                offenders.append((rel, node.lineno, name))

    assert not offenders, (
        'the add-on imports something it does not ship and Kodi does not '
        'provide:\n' + _report(offenders))
    assert visited >= 20, (
        'only %d import statements were visited; the vendored tree is not in '
        'place, so this sweep would pass without having checked it' % visited)


def test_tree_compiles():
    # The only check here that catches a regex rewrite which ate a character:
    # such a file greps clean and fails at import.
    assert compileall.compile_dir(
        str(REPO / 'resources'), quiet=2, force=True, legacy=False), \
        'a file under resources/ does not compile'
    for rel in ('entrypoint.py', 'service.py'):
        assert compileall.compile_file(
            str(REPO / rel), quiet=2, force=True, legacy=False), \
            '%s does not compile' % rel


# ---------------------------------------------------------------------------
# The eval swap (VND-05)
# ---------------------------------------------------------------------------

def test_no_eval():
    # Both patterns are anchored on the function name itself, so re.compile is
    # not a false positive for either.
    patterns = [r'\beval\s*\(', r'\bexec\s*\(']
    hits = []
    for pattern in patterns:
        hits.extend(h for h in source_scan(re.compile(pattern))
                    if h[0].endswith('.py'))
    assert not hits, (
        'dynamic code execution survives in the store or the cache:\n' +
        _report(hits))


def test_store_json_roundtrip():
    # An account dict as account.py stores it, with a non-ASCII display name.
    account = {
        'id': 'me',
        'display_name': 'Nguyễn Tiến Đạt',
        'type': 'personal',
        'drives': [
            {'id': 'b!7f3', 'name': 'OneDrive – Personal', 'type': 'personal'},
            {'id': 'b!7f4', 'name': 'Tài liệu', 'type': 'business'},
        ],
        'access_tokens': {'default': {'expires_in': 3600}},
    }

    # An export changes list of the shape export.py writes; it already coerces
    # with list(changes) at the write sites.
    export_changes = [
        {'id': '01ABC', 'name': 'Phim.mkv', 'path': '/video/Phim.mkv',
         'type': 'video', 'deleted': False},
        {'id': '01ABD', 'name': 'Nhạc.mp3', 'path': '/audio/Nhạc.mp3',
         'type': 'audio', 'deleted': True},
    ]

    # An item dict of the shape _extract_item produces: str, int, float, bool,
    # dict and list values, with last_modified_date a string and not a datetime.
    item = {
        'id': '01XYZ',
        'name': 'Ký sự.mp4',
        'name_extension': 'mp4',
        'drive_id': 'b!7f3',
        'parent': '01ROOT',
        'mimetype': 'video/mp4',
        'last_modified_date': '2026-08-22T10:11:12.123Z',
        'size': 104857600,
        'description': '',
        'deleted': False,
        'folder': {'child_count': 0},
        'video': {'width': 1920, 'height': 1080, 'duration': 3600.5},
        'thumbnail': 'https://example.invalid/thumb.jpg',
        'download_info': {'url': 'https://example.invalid/download'},
        'tags': ['a', 'b'],
    }

    for label, payload in (('account', account),
                           ('export_changes', export_changes),
                           ('item', item)):
        once = json.loads(json.dumps(payload))
        assert once == payload, '%s does not survive one JSON round trip' % label
        twice = json.loads(json.dumps(once))
        assert twice == once, (
            '%s is lossless once but not idempotent; the store round-trips a '
            'value repeatedly, so once is not enough' % label)

    # The two shapes the research identified as not surviving the repr -> json
    # swap. Asserting them documents that the write sites were checked rather
    # than assumed.
    assert json.loads(json.dumps(('a', 'b'))) != ('a', 'b'), \
        'a tuple must be known not to survive; write sites must coerce to list'
    assert json.loads(json.dumps({1: 'a'})) != {1: 'a'}, \
        'a non-string dict key must be known not to survive'


# ---------------------------------------------------------------------------
# The timeout sweep (VND-06)
# ---------------------------------------------------------------------------

def test_all_http_calls_have_timeout():
    # Request is deliberately not in this set: a Request object carries no
    # timeout, and including it would create a false requirement.
    callees = {'urlopen', 'urlretrieve'}
    found = 0
    missing = []

    for rel in tracked_files():
        if not (rel.startswith('resources/') and rel.endswith('.py')):
            continue
        tree = ast.parse(_read(rel), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                continue
            if name not in callees:
                continue
            found += 1
            if not any(kw.arg == 'timeout' for kw in node.keywords):
                missing.append((rel, node.lineno, '%s() with no timeout=' % name))

    assert not missing, (
        'an outbound HTTP call can block forever; on marginal Android TV Wi-Fi '
        'that is an unrecoverable hang:\n' + _report(missing))
    assert found >= 1, (
        'no urlopen/urlretrieve call site was found; a sweep that passes '
        'because it found nothing is the failure this guard exists to prevent')


# ---------------------------------------------------------------------------
# The manifest (ID-02, VND-11)
# ---------------------------------------------------------------------------

ADDON_ID = 'plugin.onedrive.kn'
OWN_REPO_OWNER = OWN_REPO_URL.rsplit('/', 1)[0] + '/'


@functools.lru_cache(maxsize=1)
def _addon_xml():
    return ET.parse(str(REPO / 'addon.xml')).getroot()


def test_addon_xml_identity():
    root = _addon_xml()

    assert root.get('id') == ADDON_ID, (
        'the manifest still declares %r; the add-on ships under a new id so '
        'there is no prior profile to collide with' % (root.get('id'),))
    assert root.get('version') == '1.0.0', (
        'version is %r; the lifted add-on starts its own version line at 1.0.0'
        % (root.get('version'),))

    # Non-equality rather than a pinned display string, so the maintainer can
    # adjust the presented name without editing this gate.
    name = (root.get('name') or '').strip()
    assert name, 'the manifest declares no name'
    assert name != 'OneDrive', (
        'the display name is still the upstream one; ID-02 requires a distinct '
        'name so a user can tell the two apart in the add-on browser')

    provider = (root.get('provider-name') or '').strip()
    assert provider, 'the manifest declares no provider-name'
    assert provider != 'Carlos Guzman (cguZZman)', (
        'provider-name still names the upstream author; the copyright notices '
        'stay, but the maintainer of this fork is not him')

    metadata = root.find("./extension[@point='xbmc.addon.metadata']")
    assert metadata is not None, 'the manifest has no xbmc.addon.metadata extension'
    assert metadata.find('website') is None, (
        'the metadata extension still points at addons.kodi.tv, which lists the '
        'upstream add-on and not this one')

    for field in ('source', 'forum'):
        value = (metadata.findtext(field) or '').strip()
        assert value.startswith(OWN_REPO_OWNER), (
            '<%s> is %r; it must point at this repository' % (field, value))


def test_addon_xml_imports():
    imports = _addon_xml().findall('./requires/import')
    assert len(imports) == 1, (
        'the add-on must be self-contained: expected exactly one <import>, '
        'found %r' % ([i.attrib for i in imports],))
    # 3.0.1 is the whole of the Kodi 19 rejection. Kodi 19 ships xbmc.python
    # 3.0.0 with an ABI floor of 3.0.0, so its dependency test refuses; 20 and
    # 21 ship 3.0.1 and 22 ships 3.0.2, all with the same floor, so all three
    # accept. 3.0.2 would install on Kodi 22 alone and is not an alternative.
    assert imports[0].attrib == {'addon': 'xbmc.python', 'version': '3.0.1'}, (
        'the single <import> is %r' % (imports[0].attrib,))


# ---------------------------------------------------------------------------
# Strings (D2)
# ---------------------------------------------------------------------------

# This add-on's own ids, moved down out of the script block into the 30000
# block Kodi reserves for plugins. 32012 is deleted with its settings row
# rather than renumbered, so there is no 30012.
#
# 30036-30058 is the sign-in copy: the dialog, the countdown, the account-list
# labels and one sentence per outcome in resources/lib/auth/errors.py. 30059 is
# re-authorisation's one refusal that is not a provider outcome -- the person
# signed in as somebody else on their phone -- and was added when that handler
# was written, because it was the one case nobody anticipated. It was
# added as one contiguous block in one commit, with this set widened in the
# same commit, because the assertion below is an exact equality -- an addition
# that leaves this set alone turns a green gate red and hands the next plan a
# failure it did not cause.
#
# 30070-30071 are the label and the help of the custom application identifier,
# added with the setting itself when the settings file moved to the versioned
# schema. They are the last pair, for the same reason and under the same rule.
#
# 30030, 30031 and 30033 are absent from the middle of that third run, and the
# gap is deliberate. They labelled the error-reporting category, its one row and
# the row holding the replaced sign-in host; all three rows are gone, so the
# strings went with them in the same commit as this narrowing. Renumbering the
# survivors downwards to close the gap would move labels that the settings file
# and the sign-in copy reference by number.
ADDON_STRING_IDS = (set(range(30000, 30012)) | set(range(30017, 30021))
                    | {30032, 30034, 30035} | set(range(30036, 30060))
                    | set(range(30067, 30070)) | set(range(30070, 30072)))
# The vendored module's contiguous block, left exactly where it was: the module
# resolves some of these dynamically and one is persisted, so a mechanical
# renumber cannot see them and would invalidate stored data.
MODULE_STRING_IDS = set(range(32000, 32089))
EXPECTED_STRING_IDS = ADDON_STRING_IDS | MODULE_STRING_IDS

# Ids no static scan can see. Hard-coded, which is what makes the reachability
# assertion complete rather than approximately complete.
DYNAMIC_EXCEPTION_IDS = {32065, 32018, 32021}   # raised as UIException messages
DYNAMIC_SCHEDULE_IDS = {32081, 32082}           # persisted export schedule types

PO_FILES = {
    'en_gb': 'resources/language/resource.language.en_gb/strings.po',
    'he_il': 'resources/language/resource.language.he_il/strings.po',
}


def _po_ids(rel):
    return [int(i) for i in re.findall(r'msgctxt "#(\d+)"', _read(rel))]


# The helper that picks a catalogue from an id, and the constant it picks with.
LOCALIZE_MODULE = 'resources/lib/vendor/clouddrive_common/ui/utils.py'
LOCALIZE_FLOOR_CONSTANT = 'ADDON_STRING_FLOOR'


def test_localize_owns_this_addons_block():
    """The boundary between Kodi's catalogue and this add-on's.

    KodiUtils.localize routes an id below the boundary to Kodi's own catalogue
    and everything else to an add-on's. The boundary was 32000, which was right
    while the only add-on ids in the tree were the vendored module's
    32000-32088, and wrong from the moment this add-on's own strings were
    renumbered into the 30000 block -- wrong silently, because an id in that
    block came back as Kodi's string of the same number rather than as an error.

    Asserting the constant against ADDON_STRING_IDS rather than against a
    literal is the point: the same set the catalogue is partitioned against
    decides where the boundary has to be, so moving this add-on's block again
    cannot leave the helper behind.
    """
    tree = ast.parse(_read(LOCALIZE_MODULE), filename=LOCALIZE_MODULE)
    values = [node.value.value for node in ast.walk(tree)
              if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == LOCALIZE_FLOOR_CONSTANT
                      for t in node.targets)
              and isinstance(node.value, ast.Constant)
              and isinstance(node.value.value, int)]
    assert len(values) == 1, (
        '%s defines %s %d times; expected exactly one, so this assertion knows '
        'which one it is checking' % (LOCALIZE_MODULE, LOCALIZE_FLOOR_CONSTANT,
                                      len(values)))

    floor = values[0]
    assert floor <= min(ADDON_STRING_IDS), (
        "the catalogue boundary is %d, which is above this add-on's lowest own "
        'id, %d. Every id between the two resolves against Kodi\'s catalogue '
        'and comes back as a different sentence, with nothing raised and '
        'nothing logged.' % (floor, min(ADDON_STRING_IDS)))

    localize = [node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == 'localize']
    assert len(localize) == 1, (
        '%s has %d localize definitions; the assertion above is anchored on '
        'there being one' % (LOCALIZE_MODULE, len(localize)))
    names = set()
    for node in ast.walk(localize[0]):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    assert LOCALIZE_FLOOR_CONSTANT in names, (
        'localize does not read %s, so the constant above is decoration and '
        'the comparison it is meant to control is a literal somewhere else'
        % LOCALIZE_FLOOR_CONSTANT)


def test_string_ids_partitioned():
    assert len(ADDON_STRING_IDS) == 48, (
        'the add-on owns 22 of the renumbered ids -- three of the original 25 '
        'went with the settings rows they labelled -- the 23 the sign-in copy '
        "added, re-authorisation's wrong-account refusal, and the label and "
        'help of the custom application identifier')
    assert len(MODULE_STRING_IDS) == 89, 'the module owns 89 ids'

    sets = {}
    for language, rel in PO_FILES.items():
        ids = _po_ids(rel)
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        assert not duplicates, (
            '%s declares these ids twice: %r' % (rel, duplicates))
        sets[language] = set(ids)

    en_gb = sets['en_gb']
    assert en_gb == EXPECTED_STRING_IDS, (
        'en_gb is not the expected partition.\n  unexpected: %r\n  missing: %r'
        % (sorted(en_gb - EXPECTED_STRING_IDS),
           sorted(EXPECTED_STRING_IDS - en_gb)))

    assert 30012 not in en_gb, (
        '30012 must not exist: the string it would carry ("Open Cloud Drive '
        'Common Settings") is deleted along with its settings row rather than '
        'renumbered')
    # 32012 is the *module's* own string ("Yes! Count me in") and stays. Only
    # this add-on's 32012 is deleted, and it is deleted rather than moved, so
    # the absence that can be asserted by id alone is 30012's. The settings row
    # itself is gated separately by test_directory_listing_default_off.
    assert 32012 in en_gb, (
        '32012 belongs to the vendored module and must survive; the module '
        'block 32000-32088 is contiguous')

    he_il = sets['he_il']
    assert he_il <= EXPECTED_STRING_IDS, (
        'he_il declares ids outside the partition: %r'
        % (sorted(he_il - EXPECTED_STRING_IDS),))
    assert set(range(30000, 30012)) <= he_il, (
        'he_il lost a translation in the renumber; missing: %r'
        % (sorted(set(range(30000, 30012)) - he_il),))

    # Reachability: every id named statically must resolve.
    referenced = set()
    settings = _read('resources/settings.xml')
    referenced.update(int(i) for i in re.findall(r'label="(\d+)"', settings))
    referenced.update(int(i) for i in re.findall(r'<label>(\d+)</label>', settings))
    for rel in python_sources():
        contents = _read(rel)
        referenced.update(int(i) for i in re.findall(
            r'getLocalizedString\(\s*(\d+)', contents))
        referenced.update(int(i) for i in re.findall(
            r'\blocalize\(\s*(\d+)', contents))

    # Below 30000 is a Kodi core string and is not ours to declare.
    unresolved = sorted(i for i in referenced if i >= 30000 and i not in en_gb)
    assert not unresolved, (
        'these ids are referenced but declared nowhere in en_gb: %r' % (unresolved,))

    for label, dynamic in (('UIException', DYNAMIC_EXCEPTION_IDS),
                           ('export schedule type', DYNAMIC_SCHEDULE_IDS)):
        missing = sorted(dynamic - en_gb)
        assert not missing, (
            'these %s ids are resolved at runtime and cannot be seen by a '
            'static scan, so their absence would surface only to a user: %r'
            % (label, missing))


# ---------------------------------------------------------------------------
# Settings (recorded deviations)
# ---------------------------------------------------------------------------

def test_directory_listing_default_off():
    tree = ET.parse(str(REPO / 'resources' / 'settings.xml')).getroot()

    listing = [n for n in tree.iter('setting')
               if n.get('id') == 'allow_directory_listing']
    assert len(listing) == 1, (
        'expected exactly one allow_directory_listing setting, found %d'
        % len(listing))
    node = listing[0]
    default = node.get('default')
    if default is None:
        child = node.find('default')
        default = (child.text or '').strip() if child is not None else None
    assert default == 'false', (
        'allow_directory_listing defaults to %r; on first run under the new '
        'add-on id that binds an unauthenticated loopback listener serving an '
        'enumerable index of the whole drive. This is a recorded deviation, '
        'not an accident' % (default,))

    # The old schema put a row's built-in function in an `action` attribute;
    # the versioned one puts it in a `<data>` child. Reading only the attribute
    # would leave this assertion permanently, invisibly green once the file was
    # converted -- it would still run, and it would no longer be able to fail.
    # Both forms are read so that the conversion costs the gate nothing.
    stale = []
    for n in tree.iter('setting'):
        data = n.find('data')
        written = [n.get('action') or '', (data.text or '') if data is not None else '']
        if any('_open_common_settings' in w for w in written):
            stale.append(n.get('id'))
    assert not stale, (
        "a settings row still opens the module's own settings dialog, which "
        'no longer exists as a separate add-on: %r' % (stale,))


# ---------------------------------------------------------------------------
# Merged resources (VND-03, VND-08)
# ---------------------------------------------------------------------------

SKIN_DIR = 'resources/skins/default/1080i'
MEDIA_DIR = 'resources/skins/default/media'
SKIN_XML = ('pin-dialog.xml', 'export-main-dialog.xml', 'export-schedule-dialog.xml')
SKIN_MEDIA = ('black.png', 'dialog-bg.png', 'white.png', 'dialogbutton-fo.png',
              'dialogbutton-nofo.png', 'radio-button-on.png', 'radio-button-off.png')
VENDOR_DIR = 'resources/lib/vendor/'


def test_resources_merged():
    for rel in (SKIN_DIR, MEDIA_DIR):
        assert (REPO / rel).is_dir(), '%s is missing; the skin tree was not merged' % rel

    # A second importable top-level `resources` package makes every import in
    # the add-on ambiguous, and Kodi 20's sys.path ordering amplifies it.
    stray = sorted({rel for rel in tracked_files()
                    if rel.startswith(VENDOR_DIR)
                    and 'resources' in PurePosixPath(rel).parts[3:-1]})
    assert not stray, (
        'a second `resources` package was copied into the vendored tree:\n' +
        '\n'.join(stray))
    vendor = REPO / VENDOR_DIR
    on_disk = sorted(p.relative_to(REPO).as_posix()
                     for p in vendor.rglob('resources')
                     if p.is_dir()) if vendor.is_dir() else []
    assert not on_disk, (
        'a `resources` directory exists inside the vendored tree:\n' +
        '\n'.join(on_disk))

    pt_br = REPO / 'resources/language/resource.language.pt_br'
    assert not pt_br.exists(), (
        'the upstream pt_br strings were copied; they are excluded from the '
        'lift and would carry the module id space alone')

    for rel in ('resources/lib/vendor/__init__.py',
                'resources/lib/vendor/clouddrive_common/__init__.py'):
        assert (REPO / rel).is_file(), (
            '%s is missing; the vendored tree is not an importable package' % rel)

    settings = [rel for rel in tracked_files()
                if rel.startswith('resources/')
                and PurePosixPath(rel).name == 'settings.xml']
    assert settings == ['resources/settings.xml'], (
        "exactly one settings.xml belongs under resources/; the module's own "
        'file has never been the live one and is dropped. Found: %r' % (settings,))


def test_skin_assets_present():
    skin = REPO / SKIN_DIR
    media = REPO / MEDIA_DIR

    for name in SKIN_XML:
        assert (skin / name).is_file(), (
            '%s/%s is missing; WindowXMLDialog raises "XML File for Window is '
            'missing" at construction time' % (SKIN_DIR, name))

    for name in SKIN_MEDIA:
        assert (media / name).is_file(), '%s/%s is missing' % (MEDIA_DIR, name)

    broken = []
    for name in SKIN_XML:
        root = ET.parse(str(skin / name)).getroot()
        for element in root.iter():
            references = []
            if element.tag == 'texture':
                references.append(('<texture>', element.text))
            for attribute, value in element.attrib.items():
                if value.strip().lower().endswith('.png'):
                    references.append((attribute, value))
            for where, raw in references:
                value = (raw or '').strip()
                if not value:
                    # An empty texture value is a failure, not nothing to check.
                    broken.append((name, where, '<empty>'))
                elif not (media / value).is_file():
                    broken.append((name, where, value))
    assert not broken, (
        'these skin references do not resolve under %s:\n%s'
        % (MEDIA_DIR, '\n'.join('%s: %s = %s' % b for b in broken)))


# ---------------------------------------------------------------------------
# Provenance (VND-01, VND-07, VND-09, ID-04)
# ---------------------------------------------------------------------------

UPSTREAM_COMMIT = 'df68e9a589a6faef2b3228f7520e77729bc05d9b'
UPSTREAM_URL = 'https://github.com/cguZZman/script.module.clouddrive.common'


def test_licences_present():
    assert (REPO / 'LICENSE.txt').is_file(), 'the GPL-3.0 text is missing from the root'

    apache = REPO / 'resources/lib/vendor/clouddrive_common/cache/LICENSE'
    assert apache.is_file(), (
        'the Apache-2.0 file that travels with the cache subtree is missing; '
        'it is preserved verbatim, in place, beside cache.py')
    assert 'Apache License' in apache.read_text(encoding='utf-8', errors='replace')

    bsd = REPO / 'resources/lib/vendor/pyqrcode/LICENSE.md'
    assert bsd.is_file(), "pyqrcode's BSD-3-Clause licence is missing"
    assert 'Michael Nooner' in bsd.read_text(encoding='utf-8', errors='replace')

    png = REPO / 'resources/lib/vendor/pyqrcode/png.py'
    assert png.is_file(), 'pypng is missing; pyqrcode renders nothing without it'
    assert 'Johann C. Rocholl' in png.read_text(encoding='utf-8', errors='replace'), (
        'the MIT header inside png.py is the notice; it must stay intact')


def test_vendored_sha_recorded():
    vendored = REPO / 'VENDORED.md'
    assert vendored.is_file(), 'VENDORED.md is missing'
    contents = vendored.read_text(encoding='utf-8', errors='replace')
    for label, value in (('commit', UPSTREAM_COMMIT),
                         ('branch', 'matrix'),
                         ('version', '1.4.0'),
                         ('upstream URL', UPSTREAM_URL)):
        assert value in contents, (
            'VENDORED.md does not record the %s (%s)' % (label, value))


def _markdown_sections(text):
    sections = {}
    heading = None
    for line in text.splitlines():
        match = re.match(r'^#{1,6}\s+(.*?)\s*$', line)
        if match:
            heading = match.group(1)
            sections.setdefault(heading, [])
        elif heading is not None:
            sections[heading].append(line)
    return {k: '\n'.join(v) for k, v in sections.items()}


def _section(sections, phrase):
    needle = phrase.lower()
    for heading, body in sections.items():
        if needle in heading.lower():
            return body
    return None


def test_vendored_md_sections():
    vendored = REPO / 'VENDORED.md'
    assert vendored.is_file(), 'VENDORED.md is missing'
    sections = _markdown_sections(
        vendored.read_text(encoding='utf-8', errors='replace'))

    required = ('Upstream', 'Licences', 'Excluded from the copy',
                'Local modifications', 'Service extension point',
                'Recorded behaviour deviations')
    # Match on headings, so a stub file fails.
    absent = [phrase for phrase in required if _section(sections, phrase) is None]
    assert not absent, (
        'VENDORED.md has no heading for: %r (found: %r)'
        % (absent, sorted(sections)))

    service = _section(sections, 'Service extension point')
    for name in ('SourceService', 'SourceRedirector'):
        assert name in service, (
            'the service section must name %s, so a later reader can tell '
            '"considered and discarded" from "overlooked"' % name)

    deviations = _section(sections, 'Recorded behaviour deviations')
    assert 'allow_directory_listing' in deviations, (
        'the deviations section must name allow_directory_listing; otherwise '
        'the default change reads as a regression')


def test_credits_content():
    credits = REPO / 'CREDITS.md'
    assert credits.is_file(), 'CREDITS.md is missing'
    contents = credits.read_text(encoding='utf-8', errors='replace')
    required = ('plugin.onedrive', 'Carlos Guzman',
                'script.module.clouddrive.common',
                'PyQRCode', 'Michael Nooner', 'pypng', 'Johann C. Rocholl',
                'GPL-3.0', 'BSD-3-Clause', 'MIT', 'Apache-2.0')
    absent = [value for value in required if value not in contents]
    assert not absent, 'CREDITS.md does not name: %r' % (absent,)


# ---------------------------------------------------------------------------
# The registration runbook (SETUP-04)
#
# This is what the fifth entry in EXCLUDED_DOCS buys. The runbook is excluded
# from the literal sweeps because it must quote a response that names the two
# credential parameters; in exchange the file is read here by name and its
# load-bearing contents are asserted, so the exclusion is a stronger gate rather
# than a hole. Same trade as the four documents above.
# ---------------------------------------------------------------------------

RUNBOOK = 'docs/AZURE-REGISTRATION.md'

# The response verbatim, as PITFALLS.md Pitfall 2 records it. This is the whole
# reason SETUP-04 exists: the text invites the reader to embed a credential, and
# the runbook is where they are told not to.
AADSTS7000218 = (
    "AADSTS7000218: The request body must contain the following parameter: "
    "'client_assertion' or 'client_secret'."
)


def test_runbook_contains_aadsts7000218():
    path = REPO / RUNBOOK
    assert path.is_file(), (
        '%s is missing. The app registration is the one piece of this system '
        'that lives outside the repository, and this is the only thing that '
        'can recreate it.' % RUNBOOK)

    assert RUNBOOK in tracked_files(), (
        '%s exists but is not in the git index, so it does not ship and does '
        'not survive a fresh clone' % RUNBOOK)

    contents = _read(RUNBOOK)

    assert AADSTS7000218 in contents, (
        'the runbook does not carry the misconfiguration response verbatim.\n'
        'Expected, exactly:\n  %s\n'
        'Paraphrasing it defeats the point: the reader who hits this error '
        'searches for the string they saw.' % AADSTS7000218)

    # The instruction that the quote exists to carry. Without it the runbook
    # reproduces the misleading advice instead of correcting it.
    assert re.search(r'\*\*Do not fix this by adding a client secret\.\*\*',
                     contents), (
        'the runbook quotes the error but does not immediately forbid the '
        '"fix" it invites; the quote alone is worse than not quoting it')

    for label, value in (
            ('supported-account setting', 'AzureADandPersonalMicrosoftAccount'),
            ('public-client flag', 'isFallbackPublicClient'),
            ('public-client flag, as the portal spells it',
             'Allow public client flows'),
            ('application identifier', 'efe197b3-5c14-4d67-810f-e10406742a06')):
        assert value in contents, (
            'the runbook does not name the %s (%s); the registration cannot be '
            'recreated from it' % (label, value))
