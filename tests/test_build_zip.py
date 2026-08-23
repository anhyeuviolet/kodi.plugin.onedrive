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
"""The install-time contract of the built archive (DIST-01).

Every assertion here reads a real archive built into pytest's temporary
directory, never a description of one.

The headline assertion is the set of first path components: Kodi resolves an
installed add-on by matching the archive's single top-level directory against
the id in the manifest inside it, so "exactly one, and it equals the id" is the
whole install-time contract - and it is the part the requirement text got wrong,
having named a directory from before this add-on took its own id.

Every sweep over absence carries a non-vacuity guard first, in the convention
``tests/test_vendor_gates.py`` established: an exclusion test over an empty
archive passes and certifies nothing.

If the host has no git the build cannot run and these tests fail rather than
skip. A skipped build test would hide the one thing the build delivers.
"""

import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

import pytest

# The repository root is on sys.path via tests/conftest.py, which is also what
# makes `from resources.lib.auth import ...` resolve under a bare `pytest`.
from tools import build_addon_zip

REPO = Path(__file__).resolve().parent.parent

# The manifest is read here by pattern and in the build by the XML parser. Two
# mechanisms on purpose: if the test reused the build's own reader, a reader
# that returned the wrong id would agree with itself and pass.
_ID = re.compile(r'<addon\b[^>]*\bid="([^"]+)"')
_VERSION = re.compile(r'<addon\b[^>]*\bversion="([^"]+)"')

# The shipped tree is far larger than this. The floor is what stops the absence
# assertions below from passing over an archive that holds nothing.
MEMBER_FLOOR = 30

# Development material that must not cross into the archive. Matched on the
# first path component *inside* the top-level directory.
#
# The last entry is a different add-on's source root, and it is written here as
# a literal on purpose. The build derives that class from the index - a
# top-level directory holding an addon.xml is another add-on - and a test that
# derived it the same way would only prove the build agrees with itself. Two
# mechanisms, the same reason the manifest is read here by pattern and there by
# the XML parser. Deleting this directory from the tree is a legitimate change;
# it turns test_the_forbidden_list_names_real_directories red, which is where
# this line is meant to be edited from.
#
# '.planning' left this list when the planning record was untracked and ignored,
# ahead of the repository going public. It is not that the record became safe to
# ship - it is that a name absent from the index excludes nothing, and a sweep
# for something that cannot be there proves nothing either. The build still
# carries the exclusion as a guard against a forced add; what proves that guard
# works is the synthetic tree in this file, not this list.
FORBIDDEN = ('tests', 'tools', 'repository.onedrive.kn')


def _manifest_text():
    return (REPO / 'addon.xml').read_text(encoding='utf-8')


def manifest_id():
    match = _ID.search(_manifest_text())
    assert match, 'no id attribute found on the <addon> element of addon.xml'
    return match.group(1)


def manifest_version():
    match = _VERSION.search(_manifest_text())
    assert match, 'no version attribute found on the <addon> element of addon.xml'
    return match.group(1)


@pytest.fixture(scope='module')
def archive(tmp_path_factory):
    """One archive built from the real index, shared by the read-only checks."""
    return build_addon_zip.build(tmp_path_factory.mktemp('archive'))


@pytest.fixture(scope='module')
def members(archive):
    with zipfile.ZipFile(str(archive)) as handle:
        return handle.namelist()


def _first_components(members):
    return {PurePosixPath(name).parts[0] for name in members}


def _inner(name):
    """The path inside the top-level directory, or '' for the directory itself."""
    parts = PurePosixPath(name).parts
    return '/'.join(parts[1:])


# ---------------------------------------------------------------------------
# Non-vacuity
# ---------------------------------------------------------------------------

def test_the_archive_holds_a_real_tree(members):
    assert len(members) >= MEMBER_FLOOR, (
        'the archive holds %d member(s), below the floor of %d; every absence '
        'assertion in this file would pass vacuously over it'
        % (len(members), MEMBER_FLOOR))


# ---------------------------------------------------------------------------
# The install-time contract
# ---------------------------------------------------------------------------

def test_exactly_one_top_level_directory_and_it_is_the_manifest_id(members):
    tops = _first_components(members)
    assert len(tops) == 1, (
        'Kodi accepts an archive with exactly one top-level directory; this '
        'one has %d: %s' % (len(tops), sorted(tops)))
    assert tops == {manifest_id()}, (
        'the top-level directory is %r but the manifest inside the archive '
        'declares the id %r; Kodi matches the two and refuses the install on a '
        'mismatch' % (sorted(tops)[0], manifest_id()))


def test_the_manifest_and_both_entry_scripts_are_present(members):
    top = manifest_id()
    expected = ['%s/%s' % (top, rel)
                for rel in ('addon.xml', 'entrypoint.py', 'service.py')]
    absent = [rel for rel in expected if rel not in members]
    assert not absent, (
        'the archive is missing the files Kodi loads the add-on through:\n' +
        '\n'.join(absent))


def test_the_filename_carries_the_manifest_version(archive):
    version = manifest_version()
    assert version in archive.name, (
        'the archive is named %r and the manifest declares version %r; the two '
        'must not be able to disagree' % (archive.name, version))
    assert archive.name == '%s-%s.zip' % (manifest_id(), version), (
        'unexpected archive filename: %r' % archive.name)


def test_every_member_path_is_relative_and_forward_separated(members):
    assert len(members) >= MEMBER_FLOOR
    offenders = [name for name in members
                 if name.startswith('/') or '\\' in name or '..' in PurePosixPath(name).parts]
    assert not offenders, (
        'a member path is absolute, backslash-separated or climbs out of the '
        'top-level directory; such an archive extracts differently on the '
        'build host and the television:\n' + '\n'.join(offenders))


# ---------------------------------------------------------------------------
# Absence (T-03-07)
# ---------------------------------------------------------------------------

def test_the_planning_record_the_suite_and_the_tools_are_absent(members):
    assert len(members) >= MEMBER_FLOOR, 'guarded above; repeated so this sweep cannot pass empty'

    offenders = {}
    for name in members:
        inner = PurePosixPath(_inner(name))
        if inner.parts and inner.parts[0] in FORBIDDEN:
            offenders.setdefault(inner.parts[0], []).append(name)

    assert not offenders, (
        'development material crossed into the archive; everything listed here '
        'reaches a device and cannot be recalled:\n' +
        '\n'.join('%s:\n  %s' % (top, '\n  '.join(paths))
                  for top, paths in sorted(offenders.items())))


def test_the_forbidden_list_names_real_directories():
    """Every name in FORBIDDEN must exist in the index, or it excludes nothing.

    A name that resolves to nothing sits beside three that do and the next
    reader has to check the tree to tell them apart - the discrepancy already
    recorded against `EXCLUDED_DOCS` in the phase-3 deferred items. This is also
    what makes the sweep above meaningful: absence proves something only when
    the thing was there to be excluded.
    """
    tops = {PurePosixPath(rel).parts[0] for rel in build_addon_zip.tracked_files(REPO)}
    orphans = [name for name in FORBIDDEN if name not in tops]
    assert not orphans, (
        'these names are excluded from the archive but are not in the git '
        'index, so they exclude nothing: %s' % (orphans,))


def test_exactly_one_manifest_is_inside_the_archive(members):
    assert len(members) >= MEMBER_FLOOR
    manifests = [name for name in members
                 if PurePosixPath(name).name == 'addon.xml']
    assert manifests == ['%s/addon.xml' % manifest_id()], (
        'the archive must hold exactly one addon.xml, at the root of its single '
        'top-level directory. Found: %s' % (manifests,))


def test_a_sibling_addon_directory_is_excluded_without_being_named(tmp_path):
    """The rule is derived from the index, not written down.

    The miniature repository's sibling is called `repository.example.test`,
    which appears in no exclusion list anywhere. If the build were matching a
    literal rather than asking which directories declare themselves add-ons,
    this sibling would ship and the next one added to the real tree would too.
    """
    repo = _miniature_repo(tmp_path / 'repo', sibling='repository.example.test')

    # The fixture really created it; otherwise the assertion below is vacuous.
    assert (repo / 'repository.example.test' / 'addon.xml').is_file()

    built = build_addon_zip.build(tmp_path / 'out', repo=repo)
    with zipfile.ZipFile(str(built)) as handle:
        names = handle.namelist()

    assert len(names) >= 40, 'the miniature repository did not populate'
    leaked = sorted(name for name in names
                    if PurePosixPath(_inner(name)).parts[:1] == ('repository.example.test',))
    assert not leaked, (
        "a sibling add-on's source reached the archive, which puts a second "
        'addon.xml inside it:\n' + '\n'.join(leaked))

    manifests = [name for name in names if PurePosixPath(name).name == 'addon.xml']
    assert manifests == ['plugin.example.test/addon.xml'], manifests


def test_a_nested_manifest_does_not_exclude_its_top_level_directory(tmp_path):
    """The derived rule is depth-two only, and that bound is load-bearing.

    `resources/` holds shipped source. If a manifest anywhere beneath a
    directory excluded that whole directory, one fixture file named addon.xml
    would silently empty the archive of the add-on's own code.
    """
    repo = _miniature_repo(tmp_path / 'repo')
    nested = repo / 'resources' / 'skins' / 'addon.xml'
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text('<addon id="not.a.sibling" version="1.0.0"/>\n', encoding='utf-8')
    _git(repo, 'add', '-A')

    assert 'resources' not in build_addon_zip.sibling_addon_dirs(repo)

    built = build_addon_zip.build(tmp_path / 'out', repo=repo)
    with zipfile.ZipFile(str(built)) as handle:
        inner = {_inner(name) for name in handle.namelist()}
    assert 'resources/module_00.py' in inner, (
        'a manifest nested under resources/ excluded the whole directory; the '
        "add-on's own source is gone from the archive")
    assert 'resources/skins/addon.xml' in inner


def test_the_floor_is_a_parameter_so_a_two_file_addon_can_build(tmp_path):
    """The repository add-on is genuinely two files and must still be buildable.

    Asserted against a miniature two-file add-on rather than the real
    repository add-on, so this states the property rather than the instance.
    """
    root = tmp_path / 'tiny'
    root.mkdir()
    _git(root, 'init', '-q')
    (root / 'addon.xml').write_text(
        '<addon id="repository.example.test" name="Example" version="2.0.0" '
        'provider-name="Example"></addon>\n', encoding='utf-8')
    (root / 'icon.png').write_bytes(b'\x89PNG\r\n\x1a\n')
    _git(root, 'add', '-A')

    with pytest.raises(ValueError) as raised:
        build_addon_zip.build(tmp_path / 'refused', repo=root)
    assert 'floor' in str(raised.value), str(raised.value)

    built = build_addon_zip.build(tmp_path / 'out', repo=root, minimum_members=2)
    with zipfile.ZipFile(str(built)) as handle:
        names = sorted(handle.namelist())
    assert names == ['repository.example.test/addon.xml',
                     'repository.example.test/icon.png'], names
    assert built.name == 'repository.example.test-2.0.0.zip', built.name


def test_no_compiled_cache_reaches_the_archive(members):
    assert len(members) >= MEMBER_FLOOR
    offenders = [name for name in members
                 if '__pycache__' in PurePosixPath(name).parts
                 or name.endswith(('.pyc', '.pyo'))]
    assert not offenders, (
        'a compiled cache is in the archive; it was built by whichever Python '
        'ran on the build host, and Kodi 19-21 run 3.8 while Kodi 22 runs '
        '3.14:\n' + '\n'.join(offenders))


# ---------------------------------------------------------------------------
# The index, not a walk (the DIST-01 prohibition)
# ---------------------------------------------------------------------------

def _git(root, *args):
    subprocess.run(['git'] + list(args), cwd=str(root),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


def _miniature_repo(root, addon_id='plugin.example.test', version='9.9.9',
                    tracked_extra=40, untracked=(), sibling=None):
    """A throwaway repository shaped like this one, built in a temp directory.

    Used to drive the build over an index whose contents the test controls. The
    real repository cannot be used for that: proving that an untracked file
    stays out of the archive means creating one, and creating one inside the
    working tree of the repository under test is how a test leaves debris.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, 'init', '-q')
    (root / 'addon.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<addon id="%s" name="Example" version="%s" provider-name="Example">\n'
        '</addon>\n' % (addon_id, version), encoding='utf-8')
    (root / 'entrypoint.py').write_text('# entry\n', encoding='utf-8')
    (root / 'service.py').write_text('# service\n', encoding='utf-8')
    shipped = root / 'resources'
    shipped.mkdir(exist_ok=True)
    for index in range(tracked_extra):
        (shipped / ('module_%02d.py' % index)).write_text('# %d\n' % index, encoding='utf-8')
    for excluded in ('.planning', 'tests', 'tools'):
        directory = root / excluded
        directory.mkdir(exist_ok=True)
        (directory / 'record.py').write_text('# development material\n', encoding='utf-8')

    # A second add-on's source root, named nothing like the real one, so that a
    # build matching a literal cannot pass the test that reads this.
    if sibling:
        directory = root / sibling
        directory.mkdir(exist_ok=True)
        (directory / 'addon.xml').write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<addon id="%s" name="Sibling" version="1.2.3" provider-name="Example">\n'
            '</addon>\n' % sibling, encoding='utf-8')
        (directory / 'icon.png').write_bytes(b'\x89PNG\r\n\x1a\n')

    _git(root, 'add', '-A')

    # Written after the index is populated, so they are on disk and not in it.
    for name in untracked:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('scratch\n', encoding='utf-8')
    return root


def test_an_untracked_file_cannot_enter_the_archive(tmp_path):
    scratch = ('scratch.txt',
               'resources/leftover.strm',
               'resources/__pycache__/module_00.cpython-311.pyc')
    repo = _miniature_repo(tmp_path / 'repo', untracked=scratch)

    built = build_addon_zip.build(tmp_path / 'out', repo=repo)
    with zipfile.ZipFile(str(built)) as handle:
        names = handle.namelist()

    assert len(names) >= 40, 'the miniature repository did not populate'
    inner = {_inner(name) for name in names}
    leaked = sorted(inner & set(scratch))
    assert not leaked, (
        'an untracked file reached the archive, which means the member list '
        'came from a filesystem walk rather than the git index:\n' +
        '\n'.join(leaked))


def test_the_miniature_repository_would_expose_a_walk(tmp_path):
    """The previous test is only meaningful if the scratch files really exist.

    Without this, deleting the untracked files from the fixture would leave a
    passing test that proves nothing at all.
    """
    scratch = ('scratch.txt', 'resources/leftover.strm')
    repo = _miniature_repo(tmp_path / 'repo', untracked=scratch)
    on_disk = [name for name in scratch if (repo / name).is_file()]
    assert on_disk == list(scratch), (
        'the fixture did not create the untracked files it claims to: %s' % on_disk)


def test_the_build_refuses_an_index_below_the_floor(tmp_path):
    repo = _miniature_repo(tmp_path / 'repo', tracked_extra=0)
    with pytest.raises(ValueError) as raised:
        build_addon_zip.build(tmp_path / 'out', repo=repo)
    assert 'floor' in str(raised.value), str(raised.value)
    assert not list((tmp_path / 'out').glob('*.zip')), (
        'the build wrote an archive despite refusing the index')


def test_the_directory_name_follows_a_different_manifest(tmp_path):
    """Proof the top-level name is read, not written as a literal."""
    repo = _miniature_repo(tmp_path / 'repo', addon_id='plugin.other.id',
                           version='4.5.6')
    built = build_addon_zip.build(tmp_path / 'out', repo=repo)
    with zipfile.ZipFile(str(built)) as handle:
        tops = _first_components(handle.namelist())
    assert tops == {'plugin.other.id'}, sorted(tops)
    assert built.name == 'plugin.other.id-4.5.6.zip', built.name


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def test_two_builds_from_the_same_index_agree(tmp_path):
    first = build_addon_zip.build(tmp_path / 'first')
    second = build_addon_zip.build(tmp_path / 'second')
    with zipfile.ZipFile(str(first)) as handle:
        one = handle.namelist()
    with zipfile.ZipFile(str(second)) as handle:
        two = handle.namelist()
    assert len(one) >= MEMBER_FLOOR
    assert one == two, (
        'two builds from the same index produced different member lists; only '
        'in the first: %s; only in the second: %s'
        % (sorted(set(one) - set(two)), sorted(set(two) - set(one))))
