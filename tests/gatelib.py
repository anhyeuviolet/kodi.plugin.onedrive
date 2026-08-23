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
"""The harness every repository gate reads.

There is more than one gate file now, and a second gate file that quietly
reinvents this harness is worse than no second file: two copies of the exclusion
set drift, and a drifting exclusion set is how a gate stops checking anything
without anybody noticing. So the repository root, the index-backed file list, the
text-file list, the exclusion set, the pattern sweep and the failure report live
here and nowhere else.

Nothing here imports a Kodi module and nothing here walks the filesystem for
membership decisions -- the git index is the source of truth, so an untracked
scratch file or a compiled cache can never influence a verdict.

Failures report path and line number, never a bare count: a count cannot be acted
on. Every sweep built on this carries an explicit non-vacuity guard, because a
sweep that passes because it found nothing certifies nothing.
"""

import functools
import re
import subprocess
from pathlib import Path, PurePosixPath

# The repository root, resolved from this file's location and never from the
# current working directory, so the gate gives the same verdict from anywhere.
REPO = Path(__file__).resolve().parent.parent

# The single exclusion set, defined once. Widening it is how a gate quietly stops
# checking anything, so it lives here and nowhere else.
#
#   .planning / tests  - not shipped source; the planning record and the gate
#                        files are both required to name the constructs they
#                        forbid.
#   the four documents - VENDORED.md, CREDITS.md, COVERAGE.md and README.md are
#                        *required* to name the upstream module and the original
#                        add-on id. Forgetting them produces a gate that can never
#                        go green. They are covered instead by the positive
#                        assertions in test_vendored_sha_recorded,
#                        test_vendored_md_sections and test_credits_content.
#   the runbook        - docs/AZURE-REGISTRATION.md is *required* to quote the
#                        AADSTS7000218 response verbatim, and that response names
#                        'client_assertion' and 'client_secret'. Quoting it is the
#                        entire point of the document: it is what stops the next
#                        maintainer from "fixing" the error by embedding a
#                        credential. Softening the credential pattern to let the
#                        quote through would weaken that sweep everywhere; naming
#                        one document here weakens it in one auditable place. It
#                        is covered instead by test_runbook_contains_aadsts7000218,
#                        which reads the file by name and asserts the quote, the
#                        supported-account value and the public-client flag are
#                        all present.
EXCLUDED_TOP_LEVEL = frozenset({'.planning', 'tests'})
EXCLUDED_DOCS = frozenset({'VENDORED.md', 'CREDITS.md', 'COVERAGE.md', 'README.md',
                           'docs/AZURE-REGISTRATION.md'})

TEXT_SUFFIXES = frozenset({'.py', '.xml', '.po', '.md', '.ini', '.txt'})


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


def read(rel):
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
        result.append((rel, read(rel)))
    return tuple(result)


def excluded(rel, extra_excludes=()):
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
        if excluded(rel, extra_excludes):
            continue
        for lineno, line in enumerate(contents.splitlines(), start=1):
            candidate = transform(line) if transform else line
            if regex.search(candidate):
                hits.append((rel, lineno, line.rstrip()))
    return hits


def python_sources():
    """Tracked .py files in shipped source, under the same exclusions."""
    return [rel for rel in tracked_files()
            if rel.endswith('.py') and not excluded(rel)]


def report(hits):
    return '\n'.join('{}:{}: {}'.format(*h) for h in hits)
