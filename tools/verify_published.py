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
"""Fetch what the hosted repository actually serves, and digest it.

`build_repo.py` writes the tree and `test_build_repo.py` proves the tree is
internally consistent. Neither can say anything about what a web server hands
back, and that is the only thing Kodi ever sees. This closes that gap and is
meant to be run after every publish.

WHAT IS CHECKED, AND WHY EACH ONE

  1. Every declared URL answers. The four addresses come from
     `repository.onedrive.kn/addon.xml`, parsed, so this cannot drift from the
     manifest by being edited separately -- the same rule the generator follows.

  2. The digest of each served body equals the served `.sha256` beside it. THIS
     IS THE CHECK THAT MATTERS. Kodi refuses the whole repository on a one-byte
     disagreement between the index it downloaded and the checksum file, and a
     status code says nothing about it. A repository that fails here installs,
     reports nothing, and finds nothing.

  3. Every served body is byte-identical to the local `dist/pages` build. This
     is the one that catches a stale site, and it is why a status code and a
     self-consistent checksum are not enough between them: GitHub Pages builds
     AFTER the push returns, so a check run immediately reads the PREVIOUS
     build -- serving the old archive beside the old checksum. That state is
     self-consistent and passes check 2. It is a wrong version, never a broken
     repository, and the two failures want opposite responses: wait and re-run,
     versus stop and fix. Naming them apart is the whole point of this check.

Exit status is 0 only when all three hold for every file.
"""
from __future__ import print_function

import hashlib
import os
import sys
import urllib.request
from xml.etree import ElementTree

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, 'repository.onedrive.kn', 'addon.xml')
LOCAL_TREE = os.path.join(REPO, 'dist', 'pages')

TIMEOUT_SECONDS = 60


def declared_urls():
    """(info, checksum, datadir) read out of the repository manifest.

    Through the XML parser rather than a pattern, for the reason
    `build_addon_zip.read_identity` gives: attribute order, quoting and line
    breaks inside a tag are all free to change, and a pattern that survives
    today's formatting is one that silently stops matching.
    """
    tree = ElementTree.parse(MANIFEST)
    for extension in tree.getroot().findall('extension'):
        if extension.get('point') != 'xbmc.addon.repository':
            continue
        directory = extension.find('dir')
        if directory is None:
            raise SystemExit(
                'the manifest has no <dir> element. Kodi 20 and later serve '
                'nothing from the flat form, so this is not a shape this '
                'project can publish.')
        return (directory.findtext('info'),
                directory.findtext('checksum'),
                directory.findtext('datadir'))
    raise SystemExit('the manifest declares no xbmc.addon.repository extension')


def fetch(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        return response.status, response.read()


def local_path_for(url, datadir):
    """Where `url` should have come from in the local build, or None."""
    site_root = datadir.rsplit('/', 1)[0] + '/'
    if not url.startswith(site_root):
        return None
    return os.path.join(LOCAL_TREE, *url[len(site_root):].split('/'))


def main():
    info, checksum, datadir = declared_urls()
    if not all((info, checksum, datadir)):
        raise SystemExit('the manifest is missing <info>, <checksum> or <datadir>')

    archives = []
    for addon_id in sorted(os.listdir(os.path.join(LOCAL_TREE, 'repo'))):
        directory = os.path.join(LOCAL_TREE, 'repo', addon_id)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.endswith('.zip'):
                archives.append('%s/%s/%s' % (datadir, addon_id, name))

    if not archives:
        raise SystemExit(
            'no archive found under %s. Run tools/build_repo.py first: with an '
            'empty local tree this would check the index and report success '
            'having verified no add-on at all.' % LOCAL_TREE)

    targets = [info] + archives
    bodies = {}
    problems = []
    stale = []

    print('--- fetched -----------------------------------------------------')
    for url in targets + [checksum] + [a + '.sha256' for a in archives]:
        try:
            status, body = fetch(url)
        except Exception as error:                      # noqa: BLE001
            problems.append('%s could not be fetched: %s' % (url, error))
            print('%-58s FAILED' % url.rsplit('/', 2)[-1])
            continue

        bodies[url] = body
        local = local_path_for(url, datadir)
        verdict = 'not under the site root'
        if local is not None:
            if not os.path.isfile(local):
                verdict = 'NO LOCAL COUNTERPART'
                problems.append('%s has no counterpart at %s' % (url, local))
            else:
                with open(local, 'rb') as handle:
                    same = handle.read() == body
                verdict = 'matches the local build' if same else 'STALE OR DIVERGED'
                if not same:
                    stale.append(url)
        print('%-58s %s %7d  %s'
              % (url.rsplit('/', 2)[-1], status, len(body), verdict))

    print('\n--- what Kodi verifies ------------------------------------------')
    for target, checksum_url in [(info, checksum)] + [(a, a + '.sha256')
                                                      for a in archives]:
        if target not in bodies or checksum_url not in bodies:
            continue
        stated = bodies[checksum_url].decode('ascii').strip()
        actual = hashlib.sha256(bodies[target]).hexdigest()
        agree = stated == actual
        print('%-58s %s' % (target.rsplit('/', 1)[-1], 'OK' if agree else 'MISMATCH'))
        if not agree:
            print('  served .sha256  %s\n  digest of body  %s' % (stated, actual))
            problems.append('%s does not match its published checksum; Kodi '
                            'refuses the whole repository on this' % target)

    print()
    if problems:
        print('BROKEN — Kodi would refuse or fail to install:')
        for line in problems:
            print('  ' + line)
        return 1
    if stale:
        print('SELF-CONSISTENT BUT STALE — the site serves an older build:')
        for url in stale:
            print('  ' + url)
        print('\nGitHub Pages builds after the push returns, so this is the '
              'expected reading for the first minute or two. Kodi would install '
              'the previous version rather than fail. Wait and re-run.')
        return 2
    print('EVERYTHING AGREES — served, verified, and current.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
