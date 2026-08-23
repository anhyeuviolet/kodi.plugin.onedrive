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
"""Lay out the publishable Kodi repository (DIST-02).

Writes the tree that goes on GitHub Pages: the index every Kodi installation
polls, a digest of that index, and one directory per add-on holding its archive,
that archive's digest and its artwork.

**The manifest is the only place the URLs are written.** This tool does not know
where the repository lives; it reads ``repository.onedrive.kn/addon.xml``, takes
the ``<info>``, ``<checksum>``, ``<datadir>`` and ``<hashes>`` values out of it,
and derives every output path from them. Changing a URL there moves the file
written here, and ``tests/test_build_repo.py`` asserts the two still agree. The
alternative - a layout written down twice - is the failure that produces a
repository which installs, reports no error, and finds nothing: the manifest
promises one tree and the server holds another, and there is no screen anywhere
in Kodi that says so.

**The output tree mirrors the URL path.** ``SITE_ROOT`` is the one address
written in this file, and the output directory *is* that address. Every declared
URL must begin with it, and what follows becomes the path under ``--out-dir``.
So publishing is a copy of the whole directory to the site root, and checking a
URL is string arithmetic rather than judgement.

**Archives come from tools/build_addon_zip.py**, called once per add-on with
``repo=`` pointed at that add-on's source root. There is no second archive
builder, so the single-top-level-directory install contract DIST-01 established,
and the git index as the ship boundary, hold for the repository add-on too.

**SHA-256 throughout, no MD5.** Checked against Kodi rather than recalled - see
the comment block in ``repository.onedrive.kn/addon.xml`` for the two sources and
the four details a manifest written from memory gets wrong. In short: the
``verify`` attribute on ``<checksum>`` is what makes Kodi actually digest the
index instead of merely noticing it changed, ``<hashes>true</hashes>`` is a
deprecated alias for MD5, and Kodi's own log calls MD5 broken.

The index is written uncompressed. Kodi will decompress an ``addons.xml.gz``,
but it digests the response *before* decompressing, so with a pre-gzipped index
the checksum covers the compressed bytes - which are not stable across zlib
versions. GitHub Pages compresses on the wire anyway, and that path is
transparent to the digest.

Usage::

    python tools/build_repo.py [--out-dir DIR] [--site-root URL]

Importable: ``build(out_dir)`` writes the tree and returns a description of
every file in it, verified by re-reading what was written.
"""

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

# Imported both ways deliberately, and without touching sys.path. Run as a
# script, Python puts tools/ on the path and the bare name resolves; imported by
# the suite, the repository root is on the path and the package name resolves.
# Mutating sys.path to make one of them work is forbidden tree-wide by
# test_no_syspath_mutation, and this file is inside that sweep.
try:
    from tools import build_addon_zip
except ImportError:                                  # pragma: no cover - script
    import build_addon_zip

REPO = build_addon_zip.REPO
MANIFEST = build_addon_zip.MANIFEST

# The repository add-on: the source root whose manifest declares where all of
# this is published. Derived from the index rather than named, so it stays
# correct if the directory is renamed - there is exactly one add-on in this tree
# that carries an xbmc.addon.repository extension, and that is the definition.
REPOSITORY_EXTENSION = 'xbmc.addon.repository'

# The site the tree below is published to, and the only address written in this
# file. Everything else is read out of the repository add-on's manifest, which
# must declare URLs beginning with this one.
SITE_ROOT = 'https://anhyeuviolet.github.io/kodi.plugin.onedrive/'

DEFAULT_OUT_DIR = REPO / 'dist' / 'pages'

# The floor for the repository add-on's own archive. It is a manifest and an
# icon; the twenty-file floor build_addon_zip applies to the plugin would refuse
# it. Two is still a real floor: it catches an index that has lost the icon.
REPOSITORY_MEMBER_FLOOR = 2

# Every digest name Kodi's CDigest::TypeFromString accepts, minus md5. Refusing
# md5 here rather than merely not choosing it is DIST-02's "never MD5" made
# executable: a manifest edited to <hashes>true</hashes> - the deprecated alias
# Kodi resolves to md5 - stops the build instead of quietly publishing it.
SUPPORTED_DIGESTS = {'sha1': hashlib.sha1,
                     'sha256': hashlib.sha256,
                     'sha512': hashlib.sha512}
REFUSED_DIGESTS = {'md5', 'true'}

# DIST-05. Kodi compares versions Debian-style, which sorts 3.0.0~beta and
# 3.0.0-beta *below* 3.0.0, so a pre-release published by mistake is not merely
# untidy: the plain release that follows it looks like an upgrade and the
# pre-release itself never can. Enforced at the point of publication, because
# that is the only point where it does damage.
PLAIN_VERSION = re.compile(r'^\d+(\.\d+)*$')


class RepositoryLayout(object):
    """The four URLs out of the repository add-on's <dir>, plus what they mean.

    Nothing here is a default. Every value is read from the manifest and every
    one of them is checked, because a URL this tool merely assumed would be a
    URL nothing in the published tree has to match.
    """

    def __init__(self, info, checksum, checksum_verify, datadir, artdir, hashes):
        self.info = info
        self.checksum = checksum
        self.checksum_verify = checksum_verify
        self.datadir = datadir
        self.artdir = artdir
        self.hashes = hashes

    @property
    def urls(self):
        return (self.info, self.checksum, self.datadir, self.artdir)


def _text(element, tag):
    found = element.find(tag)
    if found is None:
        return None
    return (found.text or '').strip()


def repository_source(repo=REPO):
    """The directory holding the add-on that declares the repository extension.

    Found by reading manifests, not by matching a directory name: the extension
    point is what makes an add-on a repository, and there is exactly one.
    """
    repo = Path(repo)
    candidates = []
    for rel in build_addon_zip.tracked_files(repo):
        parts = PurePosixPath(rel).parts
        if parts[-1] != MANIFEST or len(parts) > 2:
            continue
        root = ElementTree.parse(str(repo / rel)).getroot()
        if root.find("./extension[@point='%s']" % REPOSITORY_EXTENSION) is not None:
            candidates.append(repo / PurePosixPath(rel).parent)
    if len(candidates) != 1:
        raise ValueError(
            'expected exactly one tracked add-on declaring the %s extension '
            'point; found %d: %s'
            % (REPOSITORY_EXTENSION, len(candidates),
               [str(c) for c in candidates]))
    return candidates[0]


def read_layout(repository_dir):
    """Parse and check the <dir> block. Every refusal here names its reason."""
    root = ElementTree.parse(str(Path(repository_dir) / MANIFEST)).getroot()
    extension = root.find("./extension[@point='%s']" % REPOSITORY_EXTENSION)
    if extension is None:
        raise ValueError('%s declares no %s extension point'
                         % (repository_dir, REPOSITORY_EXTENSION))

    dirs = extension.findall('dir')
    if extension.find('info') is not None:
        raise ValueError(
            'the manifest uses the flat schema, with <info> directly under the '
            'extension element. Kodi 20 removed it: Omega logs an error and the '
            'repository serves nothing. Wrap the block in <dir>')
    if len(dirs) != 1:
        raise ValueError(
            'expected exactly one <dir>; found %d. More than one means more than '
            'one published tree, and this tool lays out one' % len(dirs))
    block = dirs[0]

    checksum_element = block.find('checksum')
    if checksum_element is None:
        raise ValueError('the <dir> block declares no <checksum>')
    verify = (checksum_element.get('verify') or '').strip().lower()
    if not verify:
        raise ValueError(
            'the <checksum> element carries no verify="..." attribute. Without '
            'it Kodi fetches the file, uses it only to notice that the index '
            'changed, and never verifies anything - so a corrupted or '
            'substituted index is accepted in silence')

    datadir = _text(block, 'datadir')
    artdir = _text(block, 'artdir') or datadir      # Kodi's own default
    hashes = (_text(block, 'hashes') or '').lower()

    layout = RepositoryLayout(
        info=_text(block, 'info'),
        checksum=_text(block, 'checksum'),
        checksum_verify=verify,
        datadir=datadir,
        artdir=artdir,
        hashes=hashes,
    )

    for name, value in (('info', layout.info), ('checksum', layout.checksum),
                        ('datadir', layout.datadir)):
        if not value:
            raise ValueError('the <dir> block declares no <%s>' % name)

    for name, algorithm in (('checksum verify', layout.checksum_verify),
                            ('hashes', layout.hashes)):
        if algorithm in REFUSED_DIGESTS:
            raise ValueError(
                '%s is %r. DIST-02 forbids MD5, Kodi logs it as broken, and '
                '"true" is its deprecated alias. Use one of: %s'
                % (name, algorithm, ', '.join(sorted(SUPPORTED_DIGESTS))))
        if algorithm not in SUPPORTED_DIGESTS:
            raise ValueError(
                '%s is %r, which Kodi cannot resolve to a digest. Use one of: %s'
                % (name, algorithm, ', '.join(sorted(SUPPORTED_DIGESTS))))

    for url in layout.urls:
        if not url.startswith('https://'):
            raise ValueError(
                '%r is not https. Kodi warns in its log that a plain-HTTP '
                'repository lets anyone on the path serve an add-on of their '
                'choosing to every installation that trusts it' % (url,))

    return layout


def _relative_to_site(url, site_root):
    """The path under the output directory that answers `url`."""
    if not url.startswith(site_root):
        raise ValueError(
            '%r is not under the site root %r, so no file in the published tree '
            'can answer it. Either the manifest names a second host, or '
            '--site-root is wrong' % (url, site_root))
    rel = url[len(site_root):].strip('/')
    if not rel:
        raise ValueError('%r resolves to the site root itself' % (url,))
    parts = PurePosixPath(rel).parts
    if any(part in ('.', '..') for part in parts):
        raise ValueError('%r climbs out of the published tree' % (url,))
    return PurePosixPath(rel)


def shippable_addons(repo=REPO):
    """(source_dir, manifest_root) for every add-on this tree publishes, by id.

    Derived from the index: the root add-on, plus every top-level directory
    carrying a manifest of its own. Listing them instead would publish a stale
    list the day a third add-on is added - and the symptom of that is an
    add-on nobody can install, with nothing anywhere reporting a reason.
    """
    repo = Path(repo)
    found = {}
    sources = [repo] + [repo / name
                        for name in sorted(build_addon_zip.sibling_addon_dirs(repo))]
    for source in sources:
        root = ElementTree.parse(str(source / MANIFEST)).getroot()
        addon_id = root.get('id')
        if not addon_id:
            raise ValueError('%s declares no id' % (source / MANIFEST))
        if addon_id in found:
            raise ValueError(
                'two source directories declare the add-on id %r: %s and %s'
                % (addon_id, found[addon_id][0], source))
        found[addon_id] = (source, root)
    if not found:
        raise ValueError('no add-on manifest found under %s' % repo)
    return found


def _check_version(addon_id, version):
    if not version:
        raise ValueError('%s declares no version' % addon_id)
    if not PLAIN_VERSION.match(version):
        raise ValueError(
            '%s declares version %r. Kodi compares versions Debian-style, which '
            'sorts a pre-release suffix below the plain version, so a published '
            '%r can never be superseded by %r and the plain release looks like '
            'an upgrade from it. Publish plain versions only (DIST-05)'
            % (addon_id, version, version, version.split('~')[0].split('-')[0]))


def _assets(manifest_root):
    """Every file named under <assets>, in declaration order.

    Kodi resolves each one against artdir/<id>/, so they have to be beside the
    archive or the add-on browser shows an add-on with no artwork.
    """
    metadata = manifest_root.find("./extension[@point='xbmc.addon.metadata']")
    if metadata is None:
        return []
    assets = metadata.find('assets')
    if assets is None:
        return []
    names = []
    for child in assets:
        value = (child.text or '').strip()
        if value:
            names.append(value)
    return names


def _digest(data, algorithm):
    return SUPPORTED_DIGESTS[algorithm](data).hexdigest()


def _index_bytes(addons):
    """The addons.xml document, as the exact bytes that will be written.

    Built and digested as one byte string so that the index and its checksum
    cannot be computed from two different things - which is the single most
    common way a self-hosted repository fails, and it fails with Kodi reporting
    only that the digest was wrong.

    Newlines are written literally, so the document does not change with the
    platform. Neither does the content: an XML parser normalises CRLF to LF
    inside text by specification, so a checkout with native line endings and one
    without produce the same index.
    """
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n']
    for addon_id in sorted(addons):
        element = addons[addon_id][1]
        element.tail = None
        parts.append(ElementTree.tostring(element, encoding='unicode'))
        parts.append('\n')
    parts.append('</addons>\n')
    return ''.join(parts).encode('utf-8')


def _prepare_out_dir(out_dir, index_path):
    """Empty the output directory, refusing anything that is not ours.

    The tree is rebuilt from nothing on every run so that a file left by a
    previous version cannot be published forever - a stale archive in a
    repository is served to whoever asks for it. Recognition is by the index
    file this tool writes: a directory that does not hold one was not written by
    this tool, and removing it is not this tool's decision to make.
    """
    out_dir = Path(out_dir)
    if out_dir.exists():
        if not out_dir.is_dir():
            raise ValueError('%s is not a directory' % out_dir)
        if any(out_dir.iterdir()) and not (out_dir / index_path).is_file():
            raise ValueError(
                '%s is not empty and holds no %s, so it was not written by this '
                'tool. Refusing to delete it; choose another --out-dir or empty '
                'this one by hand' % (out_dir, index_path))
        shutil.rmtree(str(out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def build(out_dir=DEFAULT_OUT_DIR, repo=REPO, site_root=SITE_ROOT):
    """Write the publishable tree and return {relative path: sha256 of bytes}.

    Every entry is read back off disk after the write, so the returned
    description cannot claim a file the tree does not hold.
    """
    repo = Path(repo)
    if not site_root.endswith('/'):
        site_root += '/'

    repository_dir = repository_source(repo)
    layout = read_layout(repository_dir)

    index_path = _relative_to_site(layout.info, site_root)
    checksum_path = _relative_to_site(layout.checksum, site_root)
    datadir_path = _relative_to_site(layout.datadir, site_root)
    artdir_path = _relative_to_site(layout.artdir, site_root)

    for name, path in (('info', index_path), ('checksum', checksum_path)):
        if datadir_path not in path.parents:
            raise ValueError(
                '<%s> resolves to %s, which is not inside <datadir> (%s). Kodi '
                'permits that, but then there is no single directory to publish '
                'and this tool cannot lay one out' % (name, path, datadir_path))

    addons = shippable_addons(repo)
    for addon_id, (_source, root) in addons.items():
        _check_version(addon_id, root.get('version'))

    out_dir = _prepare_out_dir(out_dir, index_path)

    written = {}

    def put(rel_path, data):
        target = out_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written[str(rel_path)] = _digest(data, 'sha256')

    for addon_id in sorted(addons):
        source, root = addons[addon_id]
        version = root.get('version')
        addon_dir = datadir_path / addon_id

        # The archive, through the one archive builder. Built into its own
        # directory under the tree, which is where Kodi expects it, so there is
        # no staging copy whose bytes could differ from the published ones.
        staging = out_dir / addon_dir
        staging.mkdir(parents=True, exist_ok=True)
        floor = (REPOSITORY_MEMBER_FLOOR if source == repository_dir
                 else build_addon_zip.MINIMUM_MEMBERS)
        archive = build_addon_zip.build(staging, repo=source, minimum_members=floor)

        expected = '%s-%s.zip' % (addon_id, version)
        if archive.name != expected:
            raise ValueError(
                'the archive builder wrote %r but the index will advertise %r; '
                'Kodi resolves the download URL from the id and version in '
                'addons.xml and would ask for a file that is not there'
                % (archive.name, expected))

        archive_bytes = archive.read_bytes()
        written[str(addon_dir / archive.name)] = _digest(archive_bytes, 'sha256')

        # The sidecar Kodi falls back to. It asks for a content-<hashes> HTTP
        # header first; GitHub Pages sends none, so this file is the only route.
        put(addon_dir / ('%s.%s' % (archive.name, layout.hashes)),
            (_digest(archive_bytes, layout.hashes) + '\n').encode('ascii'))

        # Artwork, resolved the way Kodi resolves it: artdir/<id>/<declared name>.
        for asset in _assets(root):
            origin = source / PurePosixPath(asset)
            if not origin.is_file():
                raise ValueError(
                    '%s declares the asset %r, which is not in its source '
                    'directory. Kodi would request it from the published tree '
                    'and render the add-on with no artwork'
                    % (addon_id, asset))
            put(artdir_path / addon_id / PurePosixPath(asset), origin.read_bytes())

    index = _index_bytes(addons)
    put(index_path, index)
    put(checksum_path,
        (_digest(index, layout.checksum_verify) + '\n').encode('ascii'))

    _verify(out_dir, written, layout, site_root, index_path, checksum_path)
    return written


def _verify(out_dir, written, layout, site_root, index_path, checksum_path):
    """Read the tree back and check it says what the build thinks it says.

    Cheap, and it is the difference between a build that reports success and a
    build that produced a working repository. The two failures it catches -
    a checksum computed from something other than the file beside it, and a
    declared URL with no file under it - are both invisible until a television
    fails to install, with no message that names either.
    """
    for rel, digest in sorted(written.items()):
        target = out_dir / rel
        if not target.is_file():
            raise ValueError('%s was reported as written and is not on disk' % rel)
        actual = _digest(target.read_bytes(), 'sha256')
        if actual != digest:
            raise ValueError('%s on disk digests to %s, reported %s'
                             % (rel, actual, digest))

    index = (out_dir / index_path).read_bytes()
    recorded = (out_dir / checksum_path).read_text(encoding='ascii').split()[0]
    expected = _digest(index, layout.checksum_verify)
    if recorded != expected:
        raise ValueError(
            '%s holds %s but %s digests to %s. Kodi refuses the repository on '
            'exactly this and reports only the mismatch'
            % (checksum_path, recorded, index_path, expected))

    for url in layout.urls:
        rel = _relative_to_site(url, site_root)
        target = out_dir / rel
        if not (target.is_file() or target.is_dir()):
            raise ValueError(
                '%s is declared in the manifest and nothing in the published '
                'tree answers it' % url)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--out-dir', default=str(DEFAULT_OUT_DIR),
        help='directory whose contents become the site root (default: dist/pages/)')
    parser.add_argument(
        '--site-root', default=SITE_ROOT,
        help='the URL prefix --out-dir is published at (default: %s)' % SITE_ROOT)
    args = parser.parse_args(argv)

    written = build(args.out_dir, site_root=args.site_root)
    for rel in sorted(written):
        print('%s  %s' % (written[rel][:16], rel))
    print('\n%d file(s) under %s' % (len(written), args.out_dir))
    return 0


if __name__ == '__main__':
    sys.exit(main())
