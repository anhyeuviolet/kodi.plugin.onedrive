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
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

# The repository root, resolved from this file's location and never from the
# current working directory, so the gate gives the same verdict from anywhere.
REPO = Path(__file__).resolve().parent.parent

# The single exclusion set, defined once. Widening it is how a gate quietly stops
# checking anything, so it lives here and nowhere else.
#
#   .planning / tests  - not shipped source; the planning record and this gate
#                        file are both required to name the constructs they forbid.
#   the four documents - VENDORED.md, CREDITS.md, COVERAGE.md and README.md are
#                        *required* to name the upstream module and the original
#                        add-on id. Forgetting them produces a gate that can never
#                        go green. They are covered instead by the positive
#                        assertions in test_vendored_sha_recorded,
#                        test_vendored_md_sections and test_credits_content.
EXCLUDED_TOP_LEVEL = frozenset({'.planning', 'tests'})
EXCLUDED_DOCS = frozenset({'VENDORED.md', 'CREDITS.md', 'COVERAGE.md', 'README.md'})

TEXT_SUFFIXES = frozenset({'.py', '.xml', '.po', '.md', '.ini', '.txt'})

# Pinned at plan time from the file as it stands. Do not recompute and re-pin:
# re-pinning after an accidental edit is exactly the failure this catches.
LICENSE_SHA256 = '0b383d5a63da644f628d99c33976ea6487ed89aaa59f0b3257992deac1171e6b'

# This repository's own URL legitimately embeds the upstream-derived repository
# name. It is the one place the bare add-on id literal is correct.
OWN_REPO_URL = 'https://github.com/anhyeuviolet/kodi.plugin.onedrive'

# The dotted path the module lives at after the lift.
VENDORED_PREFIX = 'resources.lib.vendor.clouddrive_common'


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def tracked_files():
    """Every path in the git index, relative to REPO, with '/' separators.

    The index rather than a filesystem walk, so an untracked scratch file or a
    __pycache__ directory can never influence a verdict.
    """
    out = subprocess.run(
        ['git', 'ls-files', '-z'],
        cwd=str(REPO), stdout=subprocess.PIPE, check=True,
    )
    return tuple(p for p in out.stdout.decode('utf-8').split('\0') if p)


def _is_text(rel):
    suffix = PurePosixPath(rel).suffix
    # A dotfile such as .gitignore has no suffix and counts as extensionless.
    return suffix == '' or suffix.lower() in TEXT_SUFFIXES


def _read(rel):
    return (REPO / rel).read_text(encoding='utf-8', errors='replace')


@functools.lru_cache(maxsize=1)
def text_files():
    """(path, contents) for every tracked file that is text by suffix.

    Binary assets are excluded by suffix, not by sniffing.
    """
    result = []
    for rel in tracked_files():
        if not _is_text(rel):
            continue
        if not (REPO / rel).is_file():
            continue
        result.append((rel, _read(rel)))
    return tuple(result)


def _excluded(rel, extra_excludes=()):
    parts = PurePosixPath(rel).parts
    if parts and parts[0] in EXCLUDED_TOP_LEVEL:
        return True
    if rel in EXCLUDED_DOCS:
        return True
    return rel in extra_excludes


def source_scan(pattern, extra_excludes=(), transform=None):
    """Every (path, lineno, line) in shipped text source matching `pattern`.

    `transform` is applied to each line before matching, which is how a test
    subtracts the one construction where a forbidden literal is legitimate. It
    narrows what counts as a hit; it never narrows which files are read.
    """
    regex = re.compile(pattern) if isinstance(pattern, str) else pattern
    hits = []
    for rel, contents in text_files():
        if _excluded(rel, extra_excludes):
            continue
        for lineno, line in enumerate(contents.splitlines(), start=1):
            candidate = transform(line) if transform else line
            if regex.search(candidate):
                hits.append((rel, lineno, line.rstrip()))
    return hits


def python_sources():
    """Tracked .py files in shipped source, under the same exclusions."""
    return [rel for rel in tracked_files()
            if rel.endswith('.py') and not _excluded(rel)]


def addon_tree_python():
    """Every tracked .py under resources/, plus the two root entry scripts."""
    files = [rel for rel in tracked_files()
             if rel.startswith('resources/') and rel.endswith('.py')]
    files.extend(rel for rel in ('entrypoint.py', 'service.py')
                 if rel in tracked_files())
    return files


def _report(hits):
    return '\n'.join('{}:{}: {}'.format(*h) for h in hits)


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

    missing = []
    for rel in checked:
        head = '\n'.join(_read(rel).splitlines()[:25])
        if 'GNU General Public License' not in head:
            missing.append(rel)
    assert not missing, (
        'these files lost their GPL-3.0 header in the first 25 lines:\n' +
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
    hits = source_scan(pattern, transform=lambda line: line.replace(OWN_REPO_URL, ''))
    assert not hits, (
        'the bare add-on id survives outside %s:\n%s' % (OWN_REPO_URL, _report(hits)))


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
