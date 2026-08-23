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
"""The publish-time contract of the repository tree (DIST-02).

Every assertion here reads a real tree built into pytest's temporary directory,
never a description of one, and reads it back off disk rather than trusting what
the generator reported.

A self-hosted repository fails in a way nothing else in this project does: it
fails *silently*. Kodi installs the repository add-on, reports success, and then
finds no add-ons - or finds them and cannot download them - and the only trace is
a line in a log file that a television user has no way to read. So the properties
worth asserting are the ones whose violation produces no message:

  - the digest beside the index disagrees with the index (the single most common
    self-hosted-repository failure);
  - a URL declared in the manifest has no file under it, because the declared
    layout and the produced layout were written down twice and drifted;
  - the version in the index is not the version of the archive on disk, so Kodi
    asks for a filename that does not exist;
  - the digest beside an archive disagrees with the archive.

Independence is deliberate throughout. The digests here are taken with hashlib
directly over the bytes on disk, never through the generator's own helper; the
declared URLs are parsed out of the manifest here rather than through
``read_layout``; and the URL-to-path arithmetic is redone with a plain string
strip. A test that reused the generator's own reader would only prove the
generator agrees with itself.

Every sweep over a collection carries a non-vacuity guard first, the convention
``tests/test_vendor_gates.py`` established.

If the host has no git the archive builder cannot run and these tests fail rather
than skip.
"""

import hashlib
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

import pytest

# The repository root is on sys.path via tests/conftest.py.
from tools import build_addon_zip, build_repo

REPO = Path(__file__).resolve().parent.parent

# The real tree publishes the plugin and the repository add-on. Two is the floor
# every sweep below is guarded against: with one add-on, "every add-on appears in
# the index" is a claim about a single element and the ordering, duplication and
# per-add-on layout assertions all pass trivially.
ADDON_FLOOR = 2

# Nine files: index, its digest, and per add-on an archive, its digest and at
# least one asset. Below this the tree is not one this suite has read.
FILE_FLOOR = 9

MANIFEST = 'addon.xml'


# ---------------------------------------------------------------------------
# Helpers, none of which route through the generator
# ---------------------------------------------------------------------------

def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def declared_urls(manifest_path):
    """The <dir> block's URLs, parsed here rather than through read_layout."""
    root = ElementTree.parse(str(manifest_path)).getroot()
    block = root.find("./extension[@point='xbmc.addon.repository']/dir")
    assert block is not None, (
        '%s declares no <dir> under the repository extension point; the flat '
        'schema was removed in Kodi 20' % manifest_path)
    found = {}
    for tag in ('info', 'checksum', 'datadir', 'artdir'):
        element = block.find(tag)
        if element is not None:
            found[tag] = (element.text or '').strip()
    found.setdefault('artdir', found.get('datadir'))
    found['hashes'] = (block.findtext('hashes') or '').strip().lower()
    found['verify'] = (block.find('checksum').get('verify') or '').strip().lower()
    return found


def path_under(out_dir, url, site_root):
    """The file the tree must hold to answer `url`. Plain string arithmetic."""
    assert url.startswith(site_root), (
        '%r is not under the site root %r' % (url, site_root))
    return Path(out_dir) / url[len(site_root):].strip('/')


def _git(root, *args):
    subprocess.run(['git'] + list(args), cwd=str(root),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


# ---------------------------------------------------------------------------
# The real tree, built once
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def site(tmp_path_factory):
    """(out_dir, written) for one real build of this repository's own tree."""
    out_dir = tmp_path_factory.mktemp('site')
    written = build_repo.build(out_dir)
    return out_dir, written


@pytest.fixture(scope='module')
def out_dir(site):
    return site[0]


@pytest.fixture(scope='module')
def site_root():
    root = build_repo.SITE_ROOT
    return root if root.endswith('/') else root + '/'


@pytest.fixture(scope='module')
def manifest_path():
    return build_repo.repository_source(REPO) / MANIFEST


@pytest.fixture(scope='module')
def urls(manifest_path):
    return declared_urls(manifest_path)


@pytest.fixture(scope='module')
def index_root(out_dir, urls, site_root):
    """The parsed addons.xml, read off disk."""
    return ElementTree.parse(str(path_under(out_dir, urls['info'], site_root))).getroot()


# ---------------------------------------------------------------------------
# Non-vacuity
# ---------------------------------------------------------------------------

def test_the_tree_holds_real_files(out_dir, site):
    written = site[1]
    on_disk = sorted(p for p in Path(out_dir).rglob('*') if p.is_file())
    assert len(on_disk) >= FILE_FLOOR, (
        'the published tree holds %d file(s), below the floor of %d; every '
        'assertion in this file would pass over it having read almost nothing'
        % (len(on_disk), FILE_FLOOR))
    assert len(written) == len(on_disk), (
        'the generator reported %d file(s) and the tree holds %d; the two must '
        'be the same set' % (len(written), len(on_disk)))

    archives = [p for p in on_disk if p.suffix == '.zip']
    assert archives, 'the tree holds no archive at all'
    assert max(p.stat().st_size for p in archives) > 100 * 1024, (
        'no archive in the tree is larger than 100 KiB; the add-on source did '
        'not reach it and the digest assertions below cover nothing real')


def test_the_index_lists_at_least_the_two_known_addons(index_root):
    ids = [addon.get('id') for addon in index_root]
    assert len(ids) >= ADDON_FLOOR, (
        'the index lists %d add-on(s), below the floor of %d: %s'
        % (len(ids), ADDON_FLOOR, ids))
    assert len(set(ids)) == len(ids), 'an add-on id appears twice: %s' % (ids,)


# ---------------------------------------------------------------------------
# The digest beside the index (the common failure)
# ---------------------------------------------------------------------------

def test_the_recorded_digest_is_the_digest_of_the_index_actually_written(
        out_dir, urls, site_root):
    index = path_under(out_dir, urls['info'], site_root)
    checksum = path_under(out_dir, urls['checksum'], site_root)
    assert index.is_file(), '%s does not exist' % index
    assert checksum.is_file(), '%s does not exist' % checksum

    algorithm = urls['verify']
    assert algorithm in ('sha1', 'sha256', 'sha512'), (
        'the index is verified with %r; DIST-02 forbids MD5 and Kodi logs it as '
        'broken' % (algorithm,))

    recorded = checksum.read_text(encoding='ascii').split()[0]
    expected = hashlib.new(algorithm, index.read_bytes()).hexdigest()
    assert recorded == expected, (
        '%s holds %s but %s digests to %s. Kodi refuses the whole repository on '
        'this and reports only the mismatch, so nothing installs and nothing '
        'says why' % (checksum.name, recorded, index.name, expected))


def test_the_recorded_digest_is_lowercase_hex_of_the_right_length(
        out_dir, urls, site_root):
    """Kodi compares case-insensitively but reads the file as one token.

    The length check is what catches a digest of a *description* of the index -
    a repr, a path, a truncation - rather than of its bytes.
    """
    checksum = path_under(out_dir, urls['checksum'], site_root)
    body = checksum.read_text(encoding='ascii')
    token = body.split()[0]
    widths = {'sha1': 40, 'sha256': 64, 'sha512': 128}
    assert re.fullmatch(r'[0-9a-f]+', token), (
        'the checksum file holds %r, which is not lowercase hex' % (token,))
    assert len(token) == widths[urls['verify']], (
        'the checksum file holds %d hex characters; %s produces %d'
        % (len(token), urls['verify'], widths[urls['verify']]))


# ---------------------------------------------------------------------------
# The index parses and holds every add-on this tree ships
# ---------------------------------------------------------------------------

def test_the_index_holds_every_shipped_addon(index_root):
    """Every add-on source in the tree must appear, and nothing else.

    The expected set is rebuilt here from the git index rather than taken from
    the generator: the root manifest plus every top-level directory carrying one.
    """
    tracked = build_addon_zip.tracked_files(REPO)
    sources = [rel for rel in tracked
               if PurePosixPath(rel).name == MANIFEST
               and len(PurePosixPath(rel).parts) <= 2]
    assert len(sources) >= ADDON_FLOOR, (
        'only %d add-on manifest(s) are tracked: %s' % (len(sources), sources))

    expected = set()
    for rel in sources:
        expected.add(ElementTree.parse(str(REPO / rel)).getroot().get('id'))

    listed = {addon.get('id') for addon in index_root}
    assert listed == expected, (
        'the index and the tree disagree about which add-ons exist. Only in the '
        'index: %s. Only in the tree: %s. An add-on missing from the index is an '
        'add-on nobody can install, with nothing reporting a reason'
        % (sorted(listed - expected), sorted(expected - listed)))


def test_every_indexed_addon_carries_its_extension_points(index_root):
    """The index must encapsulate whole manifests, not just their identity.

    Kodi builds its add-on records from this document alone; an <addon> element
    stripped to its attributes yields an add-on with no extension point, which
    installs and does nothing.
    """
    assert len(list(index_root)) >= ADDON_FLOOR
    bare = [addon.get('id') for addon in index_root
            if not addon.findall('./extension')]
    assert not bare, (
        'these entries carry no <extension> element: %s' % (bare,))

    points = {addon.get('id'): {e.get('point') for e in addon.findall('./extension')}
              for addon in index_root}
    repository = [i for i, p in points.items() if 'xbmc.addon.repository' in p]
    assert len(repository) == 1, (
        'expected exactly one entry declaring the repository extension point, '
        'found %s' % (repository,))


def test_each_indexed_entry_matches_its_source_manifest(index_root):
    """Identity in the index equals identity in the file it was copied from."""
    listed = {addon.get('id'): addon for addon in index_root}
    assert len(listed) >= ADDON_FLOOR

    checked = 0
    for source, _root in build_repo.shippable_addons(REPO).values():
        origin = ElementTree.parse(str(source / MANIFEST)).getroot()
        entry = listed.get(origin.get('id'))
        assert entry is not None, (
            '%s declares %r and the index does not list it'
            % (source / MANIFEST, origin.get('id')))
        for attribute in ('id', 'name', 'version', 'provider-name'):
            assert entry.get(attribute) == origin.get(attribute), (
                '%s: the index says %s=%r, the source manifest says %r'
                % (origin.get('id'), attribute, entry.get(attribute),
                   origin.get(attribute)))
        checked += 1
    assert checked >= ADDON_FLOOR, 'only %d entries were compared' % checked


# ---------------------------------------------------------------------------
# The declared URLs and the produced tree
# ---------------------------------------------------------------------------

def test_every_declared_url_is_answered_by_the_tree(out_dir, urls, site_root):
    """A repository whose datadir and real tree disagree finds nothing, silently."""
    checked = 0
    for tag in ('info', 'checksum', 'datadir', 'artdir'):
        url = urls.get(tag)
        assert url, 'the <dir> block declares no <%s>' % tag
        target = path_under(out_dir, url, site_root)
        assert target.exists(), (
            '<%s> is %s and nothing in the published tree answers it (expected '
            '%s). Kodi installs such a repository, reports success and then '
            'lists no add-ons' % (tag, url, target))
        checked += 1
    assert checked == 4, checked


def test_every_declared_url_is_https(urls):
    assert urls
    plain = [tag for tag, value in urls.items()
             if value and value.startswith('http://')]
    assert not plain, (
        'these are served over plain HTTP, which lets anyone on the path serve '
        'an add-on of their choosing to every installation that trusts this '
        'repository: %s' % (plain,))
    assert urls['info'].startswith('https://'), urls['info']


def test_each_archive_sits_where_kodi_composes_its_url(
        out_dir, urls, site_root, index_root):
    """Kodi builds <datadir>/<id>/<id>-<version>.zip and asks for exactly that.

    The path is rebuilt here from the index's own attributes, so this asserts
    the tree answers what the *index* promises, not what the generator intended.
    """
    datadir = path_under(out_dir, urls['datadir'], site_root)
    entries = list(index_root)
    assert len(entries) >= ADDON_FLOOR

    for addon in entries:
        addon_id = addon.get('id')
        version = addon.get('version')
        archive = datadir / addon_id / ('%s-%s.zip' % (addon_id, version))
        assert archive.is_file(), (
            'the index advertises %s %s, so Kodi will request %s; the tree does '
            'not hold it' % (addon_id, version, archive))


def test_each_archive_has_the_hash_sidecar_kodi_falls_back_to(
        out_dir, urls, site_root, index_root):
    """GitHub Pages sends no content-sha256 header, so the sidecar is the route.

    Kodi asks for the header first and falls back to <archive-url>.<hashes>.
    Without the file, resolving the download fails and no add-on installs.
    """
    algorithm = urls['hashes']
    assert algorithm in ('sha1', 'sha256', 'sha512'), (
        '<hashes> is %r. "true" is the deprecated alias for MD5, and DIST-02 '
        'forbids MD5' % (algorithm,))

    datadir = path_under(out_dir, urls['datadir'], site_root)
    checked = 0
    for addon in index_root:
        addon_id, version = addon.get('id'), addon.get('version')
        archive = datadir / addon_id / ('%s-%s.zip' % (addon_id, version))
        sidecar = archive.with_name(archive.name + '.' + algorithm)
        assert sidecar.is_file(), '%s does not exist' % sidecar

        recorded = sidecar.read_text(encoding='ascii').split()[0]
        expected = hashlib.new(algorithm, archive.read_bytes()).hexdigest()
        assert recorded == expected, (
            '%s holds %s but the archive beside it digests to %s'
            % (sidecar.name, recorded, expected))
        checked += 1
    assert checked >= ADDON_FLOOR, checked


def test_every_declared_asset_is_beside_its_archive(out_dir, urls, site_root):
    """Kodi resolves artwork against artdir/<id>/<name declared in <assets>>."""
    artdir = path_under(out_dir, urls['artdir'], site_root)
    checked = 0
    for addon_id, (source, root) in build_repo.shippable_addons(REPO).items():
        assets = build_repo._assets(root)
        for name in assets:
            published = artdir / addon_id / PurePosixPath(name)
            assert published.is_file(), (
                '%s declares the asset %r and %s does not exist; the add-on '
                'browser renders it with no artwork'
                % (addon_id, name, published))
            assert published.read_bytes() == (source / PurePosixPath(name)).read_bytes(), (
                '%s in the published tree is not the file in the source tree'
                % published)
            checked += 1
    assert checked >= ADDON_FLOOR, (
        'only %d asset(s) were checked; at least one per add-on was expected'
        % checked)


# ---------------------------------------------------------------------------
# Version agreement: index, filename, and the manifest inside the archive
# ---------------------------------------------------------------------------

def test_the_version_agrees_across_index_filename_and_inner_manifest(
        out_dir, urls, site_root, index_root):
    """Three places carry the version and all three must be the same one.

    Kodi reads the version from the index, composes the filename from it, and
    reads the manifest inside the archive after unpacking. A disagreement
    between the first two is a 404; between the first and the third it is an
    add-on that installs under one version and reports another, so the next
    update is offered forever or never.
    """
    datadir = path_under(out_dir, urls['datadir'], site_root)
    entries = list(index_root)
    assert len(entries) >= ADDON_FLOOR

    for addon in entries:
        addon_id, version = addon.get('id'), addon.get('version')
        assert version, '%s carries no version in the index' % addon_id

        archive = datadir / addon_id / ('%s-%s.zip' % (addon_id, version))
        assert archive.is_file(), archive
        assert version in archive.name, (archive.name, version)

        with zipfile.ZipFile(str(archive)) as handle:
            names = handle.namelist()
            inner_name = '%s/%s' % (addon_id, MANIFEST)
            assert inner_name in names, (
                '%s holds no %s' % (archive.name, inner_name))
            inner = ElementTree.fromstring(handle.read(inner_name))

        assert inner.get('version') == version, (
            '%s: the index says %r, the manifest inside the archive says %r'
            % (addon_id, version, inner.get('version')))
        assert inner.get('id') == addon_id, (
            '%s: the manifest inside the archive declares the id %r'
            % (addon_id, inner.get('id')))

        tops = {PurePosixPath(name).parts[0] for name in names}
        assert tops == {addon_id}, (
            '%s must hold exactly one top-level directory named %r; it holds %s'
            % (archive.name, addon_id, sorted(tops)))


def test_no_published_version_carries_a_pre_release_suffix(index_root):
    """DIST-05, asserted on the published document rather than on the source."""
    versions = [(a.get('id'), a.get('version')) for a in index_root]
    assert len(versions) >= ADDON_FLOOR
    offenders = [(i, v) for i, v in versions
                 if not re.fullmatch(r'\d+(\.\d+)*', v or '')]
    assert not offenders, (
        'Kodi compares versions Debian-style, which sorts a pre-release suffix '
        'below the plain version, so these can never be superseded: %s'
        % (offenders,))


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_two_runs_produce_the_same_tree_byte_for_byte(tmp_path):
    def snapshot(root):
        root = Path(root)
        return {str(p.relative_to(root)).replace('\\', '/'): sha256_of(p)
                for p in root.rglob('*') if p.is_file()}

    first = build_repo.build(tmp_path / 'first')
    second = build_repo.build(tmp_path / 'second')
    assert first == second, 'the two runs reported different file sets'

    one, two = snapshot(tmp_path / 'first'), snapshot(tmp_path / 'second')
    assert len(one) >= FILE_FLOOR
    assert one == two, (
        'two runs from the same index produced different bytes; only in the '
        'first: %s; only in the second: %s; differing: %s'
        % (sorted(set(one) - set(two)), sorted(set(two) - set(one)),
           sorted(k for k in set(one) & set(two) if one[k] != two[k])))


def test_a_rerun_removes_a_file_the_previous_run_left(tmp_path):
    """A stale archive in a repository is served to whoever asks for it."""
    out = tmp_path / 'site'
    build_repo.build(out)

    stale = out / 'repo' / 'plugin.stale.example' / 'plugin.stale.example-0.1.0.zip'
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b'stale')
    assert stale.is_file()

    build_repo.build(out)
    assert not stale.is_file(), (
        'a file from a previous run survived; a stale archive is downloaded by '
        'anyone whose index still names it')
    assert not stale.parent.exists()


def test_a_directory_that_is_not_ours_is_never_deleted(tmp_path):
    foreign = tmp_path / 'not-ours'
    foreign.mkdir()
    keep = foreign / 'index.html'
    keep.write_text('someone else\'s site\n', encoding='utf-8')

    with pytest.raises(ValueError) as raised:
        build_repo.build(foreign)
    assert 'not empty' in str(raised.value), str(raised.value)
    assert keep.is_file(), 'the build deleted a directory it did not write'


# ---------------------------------------------------------------------------
# The layout is derived from the manifest, not written down
# ---------------------------------------------------------------------------

def _miniature_site(root, site_root, path='downloads', hashes='sha256',
                    verify='sha256', repo_id='repository.example.test',
                    plugin_id='plugin.example.test', version='4.5.6',
                    checksum_name='addons.xml.sha256', flat=False,
                    datadir_override=None):
    """A throwaway repository declaring URLs the test chooses.

    Driving the generator over the real manifest can only ever confirm it
    reproduces one layout. Confirming the layout *follows* the manifest needs a
    manifest that says something different, and writing one inside the working
    tree under test is how a test leaves debris.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    _git(root, 'init', '-q')

    base = '%s%s' % (site_root, path)
    (root / MANIFEST).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<addon id="%s" name="Example" version="%s" provider-name="Example">\n'
        '  <extension point="xbmc.python.pluginsource" library="entrypoint.py"/>\n'
        '  <extension point="xbmc.addon.metadata">\n'
        '    <assets><icon>icon.png</icon></assets>\n'
        '  </extension>\n'
        '</addon>\n' % (plugin_id, version), encoding='utf-8')
    (root / 'entrypoint.py').write_text('# entry\n', encoding='utf-8')
    (root / 'icon.png').write_bytes(b'\x89PNG\r\n\x1a\nplugin')
    # Twenty-two, which puts the member list at twenty-five: comfortably over
    # build_addon_zip's floor of twenty and no higher. This fixture is built
    # fresh by fourteen tests, so every file in it is paid for fourteen times,
    # and nothing in this file asserts a member count. The forty it started at
    # was copied from `_miniature_repo` in test_build_zip.py, where forty is
    # load-bearing for an assertion this fixture does not make.
    shipped = root / 'resources'
    shipped.mkdir(exist_ok=True)
    for index in range(22):
        (shipped / ('module_%02d.py' % index)).write_text(
            '# %d\n' % index, encoding='utf-8')

    block = (
        '    <info>%s/addons.xml</info>\n'
        '    <checksum verify="%s">%s/%s</checksum>\n'
        '    <datadir>%s</datadir>\n'
        '    <hashes>%s</hashes>\n'
        % (base, verify, base, checksum_name,
           datadir_override if datadir_override is not None else base, hashes))
    if flat:
        extension = '  <extension point="xbmc.addon.repository">\n%s  </extension>\n' % block
    else:
        extension = ('  <extension point="xbmc.addon.repository">\n'
                     '   <dir>\n%s   </dir>\n  </extension>\n' % block)

    repository = root / repo_id
    repository.mkdir(exist_ok=True)
    (repository / MANIFEST).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<addon id="%s" name="Example Repository" version="1.0.0" '
        'provider-name="Example">\n%s'
        '  <extension point="xbmc.addon.metadata">\n'
        '    <assets><icon>icon.png</icon></assets>\n'
        '  </extension>\n'
        '</addon>\n' % (repo_id, extension), encoding='utf-8')
    (repository / 'icon.png').write_bytes(b'\x89PNG\r\n\x1a\nrepo')

    _git(root, 'add', '-A')
    return root


SITE = 'https://example.invalid/site/'


def test_the_tree_follows_a_manifest_declaring_a_different_path(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE, path='kodi/omega')
    out = tmp_path / 'out'
    written = build_repo.build(out, repo=repo, site_root=SITE)

    assert (out / 'kodi' / 'omega' / 'addons.xml').is_file(), sorted(written)
    assert (out / 'kodi' / 'omega' / 'addons.xml.sha256').is_file()
    assert (out / 'kodi' / 'omega' / 'plugin.example.test'
            / 'plugin.example.test-4.5.6.zip').is_file()
    assert (out / 'kodi' / 'omega' / 'repository.example.test'
            / 'repository.example.test-1.0.0.zip').is_file()
    assert not (out / 'repo').exists(), (
        'the tree was written at the path the real manifest uses, so the layout '
        'is hardcoded rather than read from the manifest under test')


def test_the_checksum_filename_follows_the_manifest(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE,
                           checksum_name='index-digest.txt')
    out = tmp_path / 'out'
    build_repo.build(out, repo=repo, site_root=SITE)

    named = out / 'downloads' / 'index-digest.txt'
    assert named.is_file(), 'the checksum file was not written where <checksum> points'
    assert not (out / 'downloads' / 'addons.xml.sha256').exists()

    recorded = named.read_text(encoding='ascii').split()[0]
    assert recorded == sha256_of(out / 'downloads' / 'addons.xml')


def test_the_sidecar_extension_follows_the_hashes_element(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE, hashes='sha512')
    out = tmp_path / 'out'
    build_repo.build(out, repo=repo, site_root=SITE)

    archive = (out / 'downloads' / 'plugin.example.test'
               / 'plugin.example.test-4.5.6.zip')
    sidecar = archive.with_name(archive.name + '.sha512')
    assert sidecar.is_file(), (
        'Kodi appends the <hashes> value to the archive URL; a sidecar named '
        'anything else is never requested')
    assert not archive.with_name(archive.name + '.sha256').exists()
    assert sidecar.read_text(encoding='ascii').split()[0] == \
        hashlib.sha512(archive.read_bytes()).hexdigest()


def test_the_index_digest_follows_the_verify_attribute(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE, verify='sha512')
    out = tmp_path / 'out'
    build_repo.build(out, repo=repo, site_root=SITE)

    index = out / 'downloads' / 'addons.xml'
    recorded = (out / 'downloads' / 'addons.xml.sha256').read_text(
        encoding='ascii').split()[0]
    assert recorded == hashlib.sha512(index.read_bytes()).hexdigest(), (
        'the index was digested with something other than the algorithm '
        'verify="sha512" names, so Kodi computes a different value and refuses '
        'the repository')


# ---------------------------------------------------------------------------
# Refusals, each because the failure it prevents is silent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value', ['md5', 'true'])
def test_md5_is_refused_wherever_it_is_declared(tmp_path, value):
    """DIST-02 forbids MD5; "true" is the deprecated alias Kodi resolves to it."""
    for keyword in ('hashes', 'verify'):
        repo = _miniature_site(tmp_path / ('repo-%s-%s' % (keyword, value)),
                               SITE, **{keyword: value})
        with pytest.raises(ValueError) as raised:
            build_repo.build(tmp_path / ('out-%s-%s' % (keyword, value)),
                             repo=repo, site_root=SITE)
        assert 'MD5' in str(raised.value), (keyword, value, str(raised.value))


def test_a_checksum_without_a_verify_attribute_is_refused(tmp_path):
    """Without verify=, Kodi fetches the digest and never checks anything."""
    repo = _miniature_site(tmp_path / 'repo', SITE, verify='')
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    assert 'verify' in str(raised.value), str(raised.value)


def test_the_flat_pre_dir_schema_is_refused(tmp_path):
    """Kodi 20 removed it: Omega logs an error and the repository serves nothing."""
    repo = _miniature_site(tmp_path / 'repo', SITE, flat=True)
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    message = str(raised.value)
    # The wording is asserted, not merely that something was refused. A flat
    # manifest also happens to declare zero <dir> blocks, so a generic "expected
    # one <dir>" refusal would pass a looser assertion while leaving the reader
    # no idea that the schema they used was removed from Kodi four versions ago.
    assert '<dir>' in message and 'Kodi 20' in message, message


def test_a_pre_release_version_is_refused(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE, version='4.5.6~beta1')
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    assert 'DIST-05' in str(raised.value), str(raised.value)
    assert not (tmp_path / 'out').exists() or not list(
        (tmp_path / 'out').rglob('*.zip')), (
        'the build published an archive despite refusing the version')


def test_a_url_outside_the_site_root_is_refused(tmp_path):
    """A second host means no single directory answers the manifest."""
    repo = _miniature_site(tmp_path / 'repo', SITE,
                           datadir_override='https://elsewhere.invalid/kodi')
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    assert 'site root' in str(raised.value), str(raised.value)


def test_an_index_outside_the_datadir_is_refused(tmp_path):
    """Kodi permits it; a single publishable directory does not exist for it."""
    repo = _miniature_site(tmp_path / 'repo', SITE,
                           datadir_override=SITE + 'downloads/inner')
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    assert 'datadir' in str(raised.value), str(raised.value)


def test_a_missing_asset_stops_the_build(tmp_path):
    repo = _miniature_site(tmp_path / 'repo', SITE)
    (repo / 'icon.png').unlink()
    _git(repo, 'add', '-A')
    with pytest.raises(ValueError) as raised:
        build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)
    assert 'icon.png' in str(raised.value), str(raised.value)


def test_the_miniature_site_builds_when_nothing_is_wrong(tmp_path):
    """The refusals above prove nothing unless the same fixture can succeed.

    Without this, a fixture broken in some unrelated way would raise ValueError
    for the wrong reason in every test above and all of them would pass.
    """
    repo = _miniature_site(tmp_path / 'repo', SITE)
    written = build_repo.build(tmp_path / 'out', repo=repo, site_root=SITE)

    # Stated exactly rather than as a floor: this fixture's whole output is
    # eight known files, and naming them is what makes every refusal above a
    # statement about one thing rather than about a fixture that never worked.
    assert sorted(written) == [
        'downloads/addons.xml',
        'downloads/addons.xml.sha256',
        'downloads/plugin.example.test/icon.png',
        'downloads/plugin.example.test/plugin.example.test-4.5.6.zip',
        'downloads/plugin.example.test/plugin.example.test-4.5.6.zip.sha256',
        'downloads/repository.example.test/icon.png',
        'downloads/repository.example.test/repository.example.test-1.0.0.zip',
        'downloads/repository.example.test/repository.example.test-1.0.0.zip.sha256',
    ], sorted(written)

    index = ElementTree.parse(str(tmp_path / 'out' / 'downloads' / 'addons.xml')).getroot()
    assert sorted(a.get('id') for a in index) == ['plugin.example.test',
                                                  'repository.example.test']
