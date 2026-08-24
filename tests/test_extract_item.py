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
"""What one Graph entry becomes, asserted against the recorded responses.

`resources.lib.graph.items` imports no Kodi module, so everything here runs on a
development host with no stub library and no device. That is the whole reason the
extractor was moved out of the provider.

TWO THINGS TO KNOW ABOUT THE FIXTURES THIS FILE READS.

The values in them are synthetic and the shapes are real. Every name, id, URL and
paging token was replaced by `tools/scrub_fixtures.py`; the keys, the nesting, the
HTTP statuses, the presence or absence of a facet and the number of entries on a
page were not. So an assertion here about a *shape* is an assertion about what
Graph actually sent, and an assertion about a *value* is only an assertion about
what the scrubber wrote. Every assertion below is of the first kind, except where
it says otherwise.

Some rows are CONSTRUCTED rather than read, and each says so where it is built.
A constructed row proves the handler; it does not prove the hazard exists. Where
a row is constructed because the recorded set contains no such entry, that fact
is stated -- it is the difference between "this is handled" and "this was
observed".

This file also quotes shapes and builds entries the shipped source may not. It
lives under `tests/`, which `gatelib.EXCLUDED_TOP_LEVEL` excludes from every
shipped-source sweep, and the gate files in this repository are required to name
what they forbid. `tests/test_error_map.py`'s module docstring is the precedent
for saying so at the point where it matters.
"""

import copy
import io
import json

import pytest

from resources.lib.graph.items import extract_item, merge_remote_item

FIXTURES = 'tests/fixtures/graph'


def _body(drive_class, name):
    path = '%s/%s/%s' % (FIXTURES, drive_class, name)
    with io.open(path, encoding='utf-8') as handle:
        return json.load(handle)['body']


@pytest.fixture(scope='module')
def business_folder():
    """The .mkv with a populated video facet and an empty photo, and the .srt."""
    return _body('business', 'folder_with_files.json')


# ---------------------------------------------------------------------------
# The facet decision (BROWSE-18)
# ---------------------------------------------------------------------------

# The first row is READ from the recorded capture and is the defect this closes:
# a .mkv carrying a populated `video`, an empty `photo: {}` and no `image` key at
# all. The shipped extractor asked `if 'image' in f or 'photo' in f`, and `{}` is
# present, so the video was also an image.
#
# The remaining rows are CONSTRUCTED, and the reason differs per row:
#
#   image-only        - the recorded set contains NO entry with a populated
#                       `image` facet and no `video`. This row is the positive
#                       control: without it, a pattern that simply never sets
#                       `image` would pass every other row here.
#   video-and-image   - Graph documents both on one item (a video with a poster
#                       frame) and the recorded set happens not to carry one.
#                       Constructed, because precedence that holds only in the
#                       observed ordering is not precedence.
#   empty-folder-facet- `folder: {}` is NOT observed. It is the same shape as the
#                       `photo: {}` that was, and the same truth test covers it.
#                       Defensive, not a fix to a measured defect.
#   empty-audio-facet - likewise not observed, same shape, same reasoning.
FACET_CASES = [
    pytest.param(
        {'id': 'x', 'name': 'a.mkv', 'video': {'width': 1280, 'height': 534,
                                               'duration': 5704607},
         'photo': {}},
        'video', ('image', 'audio'),
        id='video-and-empty-photo'),
    pytest.param(
        {'id': 'x', 'name': 'a.jpg', 'image': {'width': 4, 'height': 3},
         'size': 11},
        'image', ('video', 'audio'),
        id='image-only'),
    pytest.param(
        {'id': 'x', 'name': 'a.mkv', 'video': {'width': 1, 'height': 1},
         'image': {'width': 4, 'height': 3}},
        'video', ('image', 'audio'),
        id='video-and-image'),
    pytest.param(
        {'id': 'x', 'name': 'a.mp3', 'audio': {'duration': '1000'},
         'image': {'width': 4, 'height': 3}},
        'audio', ('video', 'image'),
        id='audio-beats-image'),
]


@pytest.mark.parametrize('entry,expected,absent', FACET_CASES)
def test_at_most_one_media_facet_is_set(entry, expected, absent):
    item = extract_item(entry)
    assert expected in item, (
        'expected the %r facet to be set on %r' % (expected, entry.get('name')))
    for key in absent:
        assert key not in item, (
            'an item claiming to be both a %s and a %s is routed by Kodi on one '
            'of the two and nobody chose which. %r must not be set here: %r'
            % (expected, key, key, item))


def test_the_recorded_mkv_is_a_video_and_not_an_image(business_folder):
    """The defect, read from the capture rather than constructed."""
    mkv = business_folder['value'][0]
    assert 'photo' in mkv and not mkv['photo'], (
        'this fixture is supposed to carry an EMPTY photo facet; if that '
        'changed, this test is no longer covering the defect it was written for')
    assert 'image' not in mkv, (
        'this fixture is supposed to carry no image key at all')

    item = extract_item(mkv)
    assert 'video' in item
    assert 'image' not in item, (
        'photo alone is not a type signal: Graph defines image as the facet that '
        'identifies an image and photo as EXIF metadata layered on an item that '
        'already carries image. An empty photo facet made this .mkv an image too')


def test_an_empty_facet_is_treated_as_absent():
    """`folder: {}` and `file: {}` are not observed; the shape is the observed one."""
    assert 'folder' not in extract_item(
        {'id': 'x', 'name': 'n', 'folder': {}}), (
        'a membership test treats an empty facet as present; that is what made '
        'the recorded .mkv an image, and the same shape on folder would make a '
        'file render as a browsable directory')
    assert extract_item({'id': 'x', 'name': 'n', 'file': {}})['mimetype'] is None


# ---------------------------------------------------------------------------
# Defensive reads (BROWSE-07)
# ---------------------------------------------------------------------------

def test_an_entry_with_no_id_extracts_rather_than_raising(business_folder):
    """CONSTRUCTED by deleting the key by hand.

    Not one of the 137 recorded live entries was missing `id`. This proves the
    handler, not the hazard: the guard exists because the cost of being wrong is
    a KeyError that ends a whole folder listing, not because an entry like this
    was seen.
    """
    reshaped = copy.deepcopy(business_folder['value'][0])
    del reshaped['id']
    item = extract_item(reshaped)
    assert item['id'] is None
    assert item['name'] == reshaped['name'], (
        'the rest of the mapping must survive a missing id')


def test_the_empty_entry_extracts():
    item = extract_item({})
    assert item['id'] is None
    assert item['name'] == ''
    assert item['deleted'] is False


def test_an_empty_value_list_produces_no_items():
    assert [extract_item(e) for e in []] == []


def test_extraction_is_per_entry_and_order_preserving(business_folder):
    entries = business_folder['value']
    items = [extract_item(e) for e in entries]
    assert len(items) == len(entries)
    for index, (entry, item) in enumerate(zip(entries, items)):
        assert item['name'] == entry['name'], (
            'entry %d produced item %d out of order; the browse layer pairs them '
            'positionally' % (index, index))
    # No entry's result may depend on any other: extracting one alone must give
    # the same answer as extracting it inside the list.
    for entry, item in zip(entries, items):
        assert extract_item(entry) == item


def test_the_srt_carries_no_media_facet(business_folder):
    item = extract_item(business_folder['value'][1])
    for key in ('video', 'audio', 'image', 'folder'):
        assert key not in item


# ---------------------------------------------------------------------------
# The remoteItem merge (BROWSE-16)
# ---------------------------------------------------------------------------
#
# The shared entry in personal/root_children.json is the Vault. It is the one
# entry of sixteen carrying a remoteItem, and the shape is what makes the merge
# non-obvious: `name` is on the OUTER half only, the folder facet is INSIDE
# remoteItem only, the two parentReferences name two different drives, and
# remoteItem.parentReference carries no `id` at all.
#
# So neither wholesale answer works. Substituting remoteItem for the entry -- what
# shipped -- gives the right address and an empty label. Not substituting gives
# the right label and misclassifies the Vault as a file.
#
# WHAT THESE ASSERTIONS ARE ABOUT, AND WHY THEY ARE NOT ABOUT CLASSIFICATION:
# a test asking "is the Vault classified as a file?" PASSES against the shipped
# code, because the wholesale swap did carry the folder facet across. That is
# recorded in 02-FINDINGS.md. The defect is the name and the addressing pair, so
# that is what is asserted here.
#
# The negative control below is not optional. A merge that always read remoteItem
# and always fell back would satisfy every assertion about the shared entry by
# accident; only the fifteen ordinary entries can tell that apart.


@pytest.fixture(scope='module')
def personal_root():
    return _body('personal', 'root_children.json')


@pytest.fixture(scope='module')
def shared_entry(personal_root):
    shared = [e for e in personal_root['value'] if 'remoteItem' in e]
    assert len(shared) == 1, (
        'this fixture is supposed to carry exactly one shared entry; the merge '
        'tests below are written against it by identity, not by search')
    return shared[0]


def test_the_shared_entry_keeps_the_name_the_user_chose(shared_entry):
    item = extract_item(shared_entry)
    assert item['name'] == shared_entry['name']
    assert item['name'], (
        'the wholesale substitution that shipped read remoteItem.name, which is '
        'documented optional and is absent here, so the Vault rendered as a '
        'blank row in the listing')


def test_the_shared_entry_addresses_the_remote_drive(shared_entry):
    item = extract_item(shared_entry)
    remote = shared_entry['remoteItem']
    assert item['id'] == remote['id'], (
        'the outer id does not resolve in the drive that holds the item; Graph '
        'warns the id may change when an item moves into a remote item')
    assert item['id'] != shared_entry['id']
    assert item['drive_id'] == remote['parentReference']['driveId'], (
        'the outer parentReference.driveId names the LOCAL drive; pairing it '
        'with the remote id addresses the wrong place')
    assert item['drive_id'] != shared_entry['parentReference']['driveId']


def test_the_shared_entry_is_a_folder(shared_entry):
    assert 'folder' in extract_item(shared_entry), (
        'the folder facet exists only inside remoteItem, so a merge that simply '
        'stopped substituting would classify the Vault as a file')


def test_the_shared_entry_has_no_parent(shared_entry):
    """remoteItem.parentReference carries no id, and there is no fallback."""
    assert 'id' not in shared_entry['remoteItem']['parentReference'], (
        'this fixture is supposed to carry no remote parent id')
    item = extract_item(shared_entry)
    assert not item['parent'], (
        'parent must not fall back to the outer parentReference.id: that names '
        'a folder in the LOCAL drive, and pairing it with a remote drive_id '
        'produces an address that resolves to nothing')


def test_the_shared_entry_falls_back_for_last_modified(shared_entry):
    """The fallback is load-bearing here, not defensive."""
    assert 'lastModifiedDateTime' not in shared_entry['remoteItem']
    item = extract_item(shared_entry)
    assert item['last_modified_date'] == shared_entry['lastModifiedDateTime']


def test_the_ordinary_entries_keep_their_own_address(personal_root):
    """The negative control. Without it the merge could always read remoteItem."""
    ordinary = [e for e in personal_root['value'] if 'remoteItem' not in e]
    assert len(ordinary) == 15, (
        'expected fifteen ordinary entries beside the one shared entry; if the '
        'fixture changed, this control is no longer covering what it was '
        'written for')
    for entry in ordinary:
        item = extract_item(entry)
        assert item['id'] == entry['id']
        assert item['drive_id'] == entry['parentReference']['driveId']


def test_the_remote_name_is_used_only_when_the_outer_name_is_absent():
    """CONSTRUCTED. The recorded shared entry carries no remoteItem.name at all."""
    both = {'id': 'outer', 'name': 'outer name',
            'remoteItem': {'id': 'remote', 'name': 'remote name',
                           'parentReference': {'driveId': 'd'}}}
    assert extract_item(both)['name'] == 'outer name'

    outer_missing = copy.deepcopy(both)
    del outer_missing['name']
    assert extract_item(outer_missing)['name'] == 'remote name'


def test_merge_returns_an_unshared_entry_unchanged(business_folder):
    entry = business_folder['value'][0]
    assert merge_remote_item(entry) is entry


def test_merge_does_not_mutate_its_input(shared_entry):
    before = copy.deepcopy(shared_entry)
    merge_remote_item(shared_entry)
    assert shared_entry == before, (
        'the entries come from a module-scoped fixture and from a response body '
        'the caller may read again; mutating one would make extraction depend on '
        'call order')
