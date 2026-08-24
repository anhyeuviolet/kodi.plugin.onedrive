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
"""Search without a filter Graph refuses, and files selected on the client.

WHAT WAS WRONG. Search has never worked on a business drive. `search()` set
`filter=file ne null`, and `$filter` is not among the parameters Graph documents
for the search endpoint -- the documented set is `$expand`, `$select`,
`$skipToken`, `$top` and `$orderby`. So the service answered **501 notSupported**,
naming the four fields it will filter on. That refusal is the service enforcing
its own documented surface: not a bug, not a tenant quirk. The personal drive's
200 is the anomaly, not the business drive's refusal.

There is no server-side spelling that works, so the classification moved to the
client. The cost is stated rather than hidden: a search now retrieves folders as
well as files, and the client discards rows it paid to receive.

WHERE THE EVIDENCE IN THIS FILE COMES FROM, because the three sources prove
different things and conflating them would prove none of them.

  * `personal/root_children.json` and `business/root_children.json` are RECORDED
    listing bodies with a real mix of facets -- 16 entries of which exactly 1
    carries a truthy file facet, and 121 entries of which none does. `is_file` is
    a pure predicate over one entry, so running it across a recorded listing is
    genuine evidence about real recorded shapes. **This is the dropping
    evidence.**

  * `personal/search.json` is a RECORDED search body of 195 entries, but it was
    captured THROUGH the filter this change removes. Every one of its 195 entries
    carries a file facet and none carries a folder facet, so it structurally
    cannot witness a folder being dropped. It is asserted here only for what it
    can support: that the predicate does not over-reject a real search body.
    **It is explicitly not evidence of dropping.**

  * The end-to-end path -- a folder arriving inside a *search* result and being
    dropped before the caller and before the per-page callback see it -- has no
    recorded body at all, and re-recording is unavailable to this phase because
    the recorder is untracked and imports an untracked live sign-in harness. That
    body is CONSTRUCTED here, and says so where it is built. A test that quietly
    used `personal/search.json` for this would pass whether or not the filter
    works, which is exactly the trap recorded against the Vault requirement.
"""

import io
import json

import pytest

from resources.lib.graph.items import extract_item, is_file
from resources.lib.graph.pager import collect_pages
from resources.lib.graph.params import search_parameters

FIXTURES = 'tests/fixtures/graph'


def _envelope(drive_class, name):
    with io.open('%s/%s/%s' % (FIXTURES, drive_class, name),
                 encoding='utf-8') as handle:
        return json.load(handle)


def _body(drive_class, name):
    return _envelope(drive_class, name)['body']


def _no_fetch(link):
    raise AssertionError(
        'a single-page body must not cause a follow-up request; asked for %r'
        % (link,))


# ---------------------------------------------------------------------------
# The refusal is unreachable, not merely handled (BROWSE-17)
# ---------------------------------------------------------------------------
#
# This is the negative control that keeps the rest of the file honest. A test
# that handled the recorded 501 politely would pass while search still never
# worked on a business drive. What has to be asserted is the property that
# PRODUCED the 501: that no request carries a filter, under either spelling.

FILTER_SPELLINGS = ('filter', '$filter')


def test_the_recorded_business_search_is_a_501_naming_its_filterable_fields():
    """The refusal this change makes unreachable, read from the capture."""
    envelope = _envelope('business', 'search.json')
    assert envelope['status'] == 501, (
        'this row is written against a recorded 501; if the fixture was '
        're-recorded it no longer covers what it was written for')
    assert 'error' in envelope['body'] and 'value' not in envelope['body']


def test_search_parameters_carry_no_filter_under_either_spelling():
    parameters = search_parameters()
    for spelling in FILTER_SPELLINGS:
        assert spelling not in parameters, (
            'a %r parameter on this endpoint is answered 501 notSupported, and '
            'the same parameter then leaked onto the next folder listing and was '
            'answered 400 -- so one search stopped browsing working' % spelling)
    assert sorted(parameters) == ['expand'], (
        'the expand parameter is the only one this endpoint should carry: %r'
        % (parameters,))


def test_search_parameters_are_a_fresh_mapping_each_call():
    first = search_parameters()
    first['filter'] = 'file ne null'
    assert 'filter' not in search_parameters(), (
        'the mapping a caller receives is a mapping a caller may mutate, and a '
        'shared one was mutated into the state that broke the next listing')


# ---------------------------------------------------------------------------
# The predicate, against recorded bodies (BROWSE-17)
# ---------------------------------------------------------------------------

# Counted from the committed fixtures. Written out so a fixture that changes
# shape fails these rows rather than silently making them prove less.
RECORDED_MIXES = [
    pytest.param('personal', 'root_children.json', 16, 1,
                 id='personal-root-1-file-of-16'),
    pytest.param('business', 'root_children.json', 121, 0,
                 id='business-root-0-files-of-121'),
]


@pytest.mark.parametrize('drive_class,name,total,kept', RECORDED_MIXES)
def test_the_predicate_drops_folders_in_a_recorded_listing(
        drive_class, name, total, kept):
    """THE DROPPING EVIDENCE. Recorded bodies with a real mix of facets."""
    entries = _body(drive_class, name)['value']
    assert len(entries) == total, (
        'this row is written against a %d-entry capture' % total)
    survivors = [e for e in entries if is_file(e)]
    assert len(survivors) == kept, (
        'the predicate must keep %d of %d here; %d survived'
        % (kept, total, len(survivors)))


def test_the_personal_root_remainder_is_folders_and_the_shared_vault():
    """Why 1 + 14 is 15 and not 16, so the arithmetic is not a puzzle later.

    The sixteenth entry is the shared Vault. Its folder facet lives inside its
    remoteItem, so it carries neither a truthy file facet nor a truthy outer
    folder facet -- which is precisely the shape the field-wise merge exists for.
    """
    from resources.lib.vendor.clouddrive_common.utils import Utils
    entries = _body('personal', 'root_children.json')['value']
    files = [e for e in entries if is_file(e)]
    folders = [e for e in entries if Utils.get_safe_value(e, 'folder')]
    shared = [e for e in entries if 'remoteItem' in e]
    assert (len(files), len(folders), len(shared)) == (1, 14, 1)
    assert len(files) + len(folders) + len(shared) == len(entries) == 16


def test_the_recorded_search_body_is_not_over_rejected():
    """NOT evidence of dropping. It was captured THROUGH the removed filter.

    All 195 entries carry a file facet and none carries a folder facet, because
    the filter was applied server-side when this was recorded. So the only thing
    it can prove is that the predicate does not over-reject a real search body,
    and that is the only thing asserted.
    """
    entries = _body('personal', 'search.json')['value']
    assert len(entries) == 195
    assert all(is_file(e) for e in entries), (
        'the predicate must keep every entry of a body that was already '
        'filtered to files; rejecting any of them would mean it disagrees with '
        'the server about what a file is')
    from resources.lib.vendor.clouddrive_common.utils import Utils
    assert not any(Utils.get_safe_value(e, 'folder') for e in entries), (
        'this capture is supposed to contain no folder at all; if one appears, '
        'it stopped being a filtered capture and this docstring is wrong')


def test_an_empty_file_facet_is_not_a_file():
    assert is_file({'file': {}}) is False, (
        'a membership test would call this a file; the extractor treats an empty '
        'facet as absent and this predicate must agree with it about the same '
        'entry, or the two disagree one layer apart')
    assert is_file({}) is False
    assert is_file({'folder': {'childCount': 0}}) is False
    assert is_file({'file': {'mimeType': 'video/x-matroska'}}) is True


# ---------------------------------------------------------------------------
# End to end, against a constructed body (BROWSE-17)
# ---------------------------------------------------------------------------

def _constructed_search_body():
    """CONSTRUCTED, and it has to be.

    No recorded search body contains a folder, because every search capture was
    taken through the filter this change removes, and re-recording is unavailable
    to this phase -- the recorder is untracked and imports an untracked live
    sign-in harness.

    The folder sits BETWEEN the two files on purpose: it makes the order
    assertion meaningful. A filter that dropped the last entry, or that sorted,
    would pass a body where the folder came last.
    """
    return {'value': [
        {'id': 'f1', 'name': 'first.mkv', 'file': {'mimeType': 'video/x-matroska'}},
        {'id': 'd1', 'name': 'a folder', 'folder': {'childCount': 3}},
        {'id': 'f2', 'name': 'second.srt', 'file': {'mimeType': 'text/plain'}},
    ]}


def test_a_folder_in_a_search_result_is_dropped_in_order():
    items = collect_pages(_constructed_search_body(), _no_fetch,
                          extract_item, keep=is_file)
    assert [i['name'] for i in items] == ['first.mkv', 'second.srt'], (
        'the folder must not survive, and the two files must keep the order the '
        'response listed them in; nothing here is sorted')


def test_the_per_page_callback_sees_filtered_items_not_raw_ones():
    """The reason the predicate lives in the pager and not in a comprehension.

    on_items_page_completed is what the browse layer renders from, so it must see
    the rows that will be shown. Filtering after the fact would leave the callback
    reporting rows the caller then discards -- a progress count that disagrees
    with the screen.
    """
    seen = []
    collect_pages(_constructed_search_body(), _no_fetch, extract_item,
                  keep=is_file, on_page=seen.append)
    assert len(seen) == 1
    assert [i['name'] for i in seen[0]] == ['first.mkv', 'second.srt']


def test_the_per_item_hook_also_sees_only_survivors():
    seen = []
    collect_pages(_constructed_search_body(), _no_fetch, extract_item,
                  keep=is_file, on_before_add_item=seen.append)
    assert [i['name'] for i in seen] == ['first.mkv', 'second.srt']


def test_a_search_returning_nothing_yields_an_empty_list():
    assert collect_pages({'value': []}, _no_fetch, extract_item,
                         keep=is_file) == []


def test_a_search_body_of_only_folders_yields_an_empty_list():
    body = {'value': [{'id': 'd%d' % n, 'name': 'd%d' % n,
                       'folder': {'childCount': 0}} for n in range(5)]}
    assert collect_pages(body, _no_fetch, extract_item, keep=is_file) == []


def test_filtering_spans_pages():
    """A folder on page two must be dropped as surely as one on page one."""
    page_two = {'value': [
        {'id': 'd2', 'name': 'another folder', 'folder': {'childCount': 1}},
        {'id': 'f3', 'name': 'third.ass', 'file': {'mimeType': 'text/plain'}},
    ]}
    page_one = dict(_constructed_search_body())
    page_one['@odata.nextLink'] = 'https://graph.invalid/page/2'

    fetched = []

    def fetch(link):
        fetched.append(link)
        return page_two

    items = collect_pages(page_one, fetch, extract_item, keep=is_file)
    assert [i['name'] for i in items] == ['first.mkv', 'second.srt', 'third.ass']
    assert fetched == ['https://graph.invalid/page/2']


def test_no_keep_predicate_keeps_everything():
    """The default must leave every existing caller unaffected."""
    items = collect_pages(_constructed_search_body(), _no_fetch, extract_item)
    assert len(items) == 3
