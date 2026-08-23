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
"""Build the installable archive (DIST-01).

Kodi's file-manager install resolves an add-on by matching the archive's single
top-level directory against the id in the manifest inside it; a mismatch is
refused. Both the directory name and the version in the filename are therefore
read out of ``addon.xml`` rather than written here as literals, so the archive
and the manifest cannot disagree.

The member list comes from the git index, never from a filesystem walk. A walk
ships whatever happens to be lying in the tree: a compiled cache built by a
different Python version than the one Kodi runs, a scratch file, an archive from
a previous run, and - on a bad day - a probe output holding a live credential.
The index cannot contain any of those, and every path already excluded by
``.gitignore`` is excluded here for free.

What the index does contain and the archive must not is development material:
the planning record, the test suite and this tool. Those are removed by first
path component. The rule is an exclusion list rather than an include list on
purpose: an include list silently drops a new source directory the day someone
adds one, whereas an exclusion list ships it.

Usage::

    python tools/build_addon_zip.py [--out-dir DIR]

Importable so a test can drive it into a temporary directory: ``build(out_dir)``
writes one archive and returns the path it wrote.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

# Resolved from this file rather than the working directory, so the build
# produces the same archive from anywhere.
REPO = Path(__file__).resolve().parent.parent

MANIFEST = 'addon.xml'

# Tracked, but development material rather than shipped source. Matched on the
# first path component only.
#
#   .planning - the planning record; one file under it is measurement output
#               from a live probe run.
#   tests     - the suite, including the repository gates.
#   tools     - this build itself.
EXCLUDED_TOP_LEVEL = frozenset({'.planning', 'tests', 'tools'})

# Anything shipping at all puts the member list above this. The floor exists so
# a build from an empty or broken index fails here instead of writing an archive
# that installs and does nothing.
MINIMUM_MEMBERS = 20


def read_identity(repo=REPO):
    """The (id, version) pair from the manifest, via the XML parser.

    Not a regular expression: the attribute order, the quoting style and the
    line breaks inside the tag are all free to change, and a pattern that
    survives today's formatting is a pattern that silently stops matching.
    """
    root = ElementTree.parse(str(Path(repo) / MANIFEST)).getroot()
    addon_id = root.get('id')
    version = root.get('version')
    if not addon_id or not version:
        raise ValueError(
            '%s carries no id and/or no version on its <addon> element; the '
            'archive cannot be named' % MANIFEST)
    return addon_id, version


def tracked_files(repo=REPO):
    """Every path in the git index, relative to the repository, '/' separated.

    Null-separated so a path holding a space or a non-ASCII character is read
    verbatim - the same mechanism, and for the same reason, as the helper in
    ``tests/test_vendor_gates.py``.
    """
    out = subprocess.run(
        ['git', 'ls-files', '-z'],
        cwd=str(repo), stdout=subprocess.PIPE, check=True,
    )
    return tuple(p for p in out.stdout.decode('utf-8').split('\0') if p)


def shipped_files(repo=REPO):
    """The tracked paths that belong in the archive, sorted.

    Sorted so two builds from the same index produce the same member list in the
    same order.
    """
    return sorted(
        rel for rel in tracked_files(repo)
        if PurePosixPath(rel).parts[0] not in EXCLUDED_TOP_LEVEL
    )


def build(out_dir, repo=REPO):
    """Write one archive into `out_dir` and return the path written."""
    repo = Path(repo)
    addon_id, version = read_identity(repo)

    members = shipped_files(repo)
    if len(members) < MINIMUM_MEMBERS:
        raise ValueError(
            'the git index yielded %d shipping file(s), below the floor of %d; '
            'refusing to write an archive that installs and does nothing'
            % (len(members), MINIMUM_MEMBERS))
    if MANIFEST not in members:
        raise ValueError(
            '%s is not in the member list; an archive without a manifest is not '
            'an add-on' % MANIFEST)

    # A path in the index whose file is gone fails inside zipfile with a bare
    # FileNotFoundError naming one absolute path. Name all of them here instead.
    missing = [rel for rel in members if not (repo / rel).is_file()]
    if missing:
        raise ValueError(
            'these paths are in the git index but not on disk:\n' +
            '\n'.join(missing))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ('%s-%s.zip' % (addon_id, version))

    with zipfile.ZipFile(str(target), 'w', zipfile.ZIP_DEFLATED) as archive:
        for rel in members:
            # An explicit arcname, forward-separated regardless of host, so a
            # build on Windows produces the same member names as one on Linux.
            archive.write(str(repo / rel),
                          arcname=str(PurePosixPath(addon_id) / rel))
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--out-dir', default=str(REPO / 'dist'),
        help='directory to write the archive into (default: dist/)')
    args = parser.parse_args(argv)

    written = build(args.out_dir)
    print(written)
    return 0


if __name__ == '__main__':
    sys.exit(main())
