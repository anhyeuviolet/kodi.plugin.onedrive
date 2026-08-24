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
"""Paging, cancellation and the shape of a response envelope.

THREE MEASUREMENTS THIS FILE EXISTS BECAUSE OF.

The recursion ceiling. The shipped pager called itself once per page. On CPython
3.11 with the default recursion limit of 1000 it returned every item at 500 pages
and at 900, and at both 1,000 and 1,500 pages it raised `RecursionError` after
fetching 998. Under Kodi the ceiling is lower, because the invoker,
`entrypoint.py`, the route table and `get_folder_items` are already on the stack
beneath it.

The cancel defect, traced through the source rather than inferred from the
requirement's wording. The requirement predicted a silently empty listing. What
actually happened between two pages is worse: the outer frame fetched the next
page, the inner frame's cancel check was true, the inner frame returned `None`,
and the outer frame then executed `items.extend(None)` -- a `TypeError` raised
inside the provider, surfacing as a failed listing carrying a traceback rather
than as a short one.

The committed third page. An earlier capture attempt never recorded a final page,
so termination could not be proven at all: a loop that never sees a page without
a next link is only ever observed to survive, never to stop.
`root_children_page_3.json` carries 21 entries and no next link, and it is what
makes 50 + 50 + 21 = 121 a statement about stopping.

WHAT IS READ AND WHAT IS BUILT. The termination and cancellation rows all run
against the three recorded business pages. Exactly one thing in this file is
CONSTRUCTED -- the delta-link body -- because no committed fixture carries
`@odata.deltaLink`, checked across all three page fixtures and the rest of the
set. It is labelled where it is built.
"""

import io
import json

import pytest

from resources.lib.graph.pager import collect_pages, entries_of

FIXTURES = 'tests/fixtures/graph'


def _body(drive_class, name):
    with io.open('%s/%s/%s' % (FIXTURES, drive_class, name),
                 encoding='utf-8') as handle:
        return json.load(handle)['body']


def _identity(entry):
    """The per-entry callable. The pager's contract does not involve extraction."""
    return entry


@pytest.fixture(scope='module')
def pages():
    """The three recorded business pages: 50, 50 and 21 entries."""
    return [_body('business', 'root_children_page_%d.json' % n)
            for n in (1, 2, 3)]


class ScriptedFetch(object):
    """The fetch port, positional and consumed in order.

    Running off the end raises rather than repeating the last answer, for the
    reason `FakeGraph` gives: a pager handed the last page twice looks like a
    listing that simply ended.
    """

    def __init__(self, *responses):
        self.queue = list(responses)
        self.scripted = len(responses)
        self.calls = []

    def __call__(self, link):
        self.calls.append(link)
        if not self.queue:
            raise AssertionError(
                'the fetch port was called %d time(s) but only %d response(s) '
                'were scripted; a call the test did not intend is a defect to '
                'report, not one to absorb' % (len(self.calls), self.scripted))
        return self.queue.pop(0)


# ---------------------------------------------------------------------------
# Termination and order (BROWSE-02, CI-02)
# ---------------------------------------------------------------------------

def test_three_recorded_pages_yield_every_item_and_stop(pages):
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity)

    assert len(items) == 121, (
        'the three recorded pages carry 50, 50 and 21 entries; the third has no '
        'next link and is what makes this a statement about stopping rather '
        'than about surviving')
    assert len(fetch.calls) == 2, (
        'each next page must be fetched exactly once: three pages means two '
        'follow-up requests, and a repeated fetch is a listing that shows the '
        'same rows twice')


def test_items_follow_page_order_then_entry_order(pages):
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity)

    expected = [e['id'] for page in pages for e in page['value']]
    assert [i['id'] for i in items] == expected, (
        'nothing is sorted and nothing is interleaved: page N is rendered '
        'before page N+1, and within a page the service order is kept')


def test_a_single_page_with_one_entry_yields_one_item():
    fetch = ScriptedFetch()
    body = {'value': [{'id': 'only'}]}
    assert collect_pages(body, fetch, _identity) == [{'id': 'only'}]
    assert fetch.calls == []


def test_an_empty_first_page_with_no_next_link_yields_nothing():
    fetch = ScriptedFetch()
    assert collect_pages({'value': []}, fetch, _identity) == []
    assert fetch.calls == []


def test_running_off_the_end_of_the_script_fails_loudly(pages):
    """One response too few. The pager must not loop or re-serve."""
    fetch = ScriptedFetch(pages[1])
    with pytest.raises(AssertionError) as raised:
        collect_pages(pages[0], fetch, _identity)
    assert 'only 1 response' in str(raised.value)


def test_the_page_hook_receives_each_page_as_it_completes(pages):
    seen = []
    fetch = ScriptedFetch(pages[1], pages[2])
    collect_pages(pages[0], fetch, _identity, on_page=seen.append)
    assert [len(page) for page in seen] == [50, 50, 21], (
        'on_page is the per-page escape hatch a caller uses to render '
        'progressively; it must fire once per page, with that page only')


def test_the_per_item_hook_sees_every_item_before_it_is_kept(pages):
    seen = []
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity,
                          on_before_add_item=seen.append)
    assert len(seen) == len(items) == 121


# ---------------------------------------------------------------------------
# Cancellation (BROWSE-03)
# ---------------------------------------------------------------------------

class CancelAfter(object):
    """True once `pages_seen` page boundaries have been crossed."""

    def __init__(self, after):
        self.after = after
        self.checks = 0

    def __call__(self):
        cancelled = self.checks >= self.after
        self.checks += 1
        return cancelled


CANCEL_CASES = [
    pytest.param(0, 0, id='cancel-before-first-page'),
    pytest.param(1, 1, id='cancel-after-page-1'),
    pytest.param(2, 2, id='cancel-after-page-2'),
]


@pytest.mark.parametrize('cancel_after,expected_fetches', CANCEL_CASES)
def test_cancelling_at_any_boundary_returns_an_empty_list(
        pages, cancel_after, expected_fetches):
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity,
                          cancelled=CancelAfter(cancel_after))

    assert items == [], (
        'a cancelled listing is an empty listing, never a partial one: the user '
        'cancelled because it was taking too long, and half a folder rendered '
        'as though it were the whole folder is a wrong answer they cannot tell '
        'from a right one')
    assert len(fetch.calls) == expected_fetches, (
        'the boundary check must run before the next fetch, so a cancelled run '
        'does not pay for a page it will discard')


def test_cancelling_between_pages_raises_nothing(pages):
    """The shipped shape raised TypeError here, not a quiet empty listing.

    The outer frame fetched the next page, the inner frame's cancel check was
    true, the inner returned None, and the outer ran items.extend(None).
    """
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity,
                          cancelled=CancelAfter(1))
    assert items == []


def test_a_non_cancelled_run_over_the_same_pages_returns_everything(pages):
    """The control: [] above is a cancellation result, not a broken harness."""
    fetch = ScriptedFetch(pages[1], pages[2])
    items = collect_pages(pages[0], fetch, _identity,
                          cancelled=lambda: False)
    assert len(items) == 121


# ---------------------------------------------------------------------------
# The defensive envelope read (BROWSE-07)
# ---------------------------------------------------------------------------

# All three are recorded, not constructed, and all three carry an `error` key and
# no entry list at all. The status is asserted alongside, so a fixture that was
# re-recorded as a success would fail here rather than quietly making this row
# prove nothing.
ERROR_BODIES = [
    pytest.param('business', 'root_children_leaked_filter.json', 400,
                 id='400-notSupported-leaked-filter'),
    pytest.param('personal', 'item_absent.json', 404,
                 id='404-itemNotFound'),
    pytest.param('business', 'search.json', 501,
                 id='501-notSupported-search-filter'),
]


@pytest.mark.parametrize('drive_class,name,status', ERROR_BODIES)
def test_a_body_with_no_entry_list_yields_no_entries(drive_class, name, status):
    with io.open('%s/%s/%s' % (FIXTURES, drive_class, name),
                 encoding='utf-8') as handle:
        envelope = json.load(handle)
    assert envelope['status'] == status, (
        'this row is written against a recorded %d; if the fixture was '
        're-recorded it no longer covers what it was written for' % status)
    body = envelope['body']
    assert 'error' in body and 'value' not in body, (
        'this row needs a body with an error and no entry list; that is what '
        'the shipped unconditional read turned into a traceback')
    assert entries_of(body) == [], (
        'reading the entry key unconditionally is what turns a recorded error '
        'body into a KeyError traceback from inside the provider instead of an '
        'empty listing')


@pytest.mark.parametrize('body', [
    pytest.param(None, id='none'),
    pytest.param({}, id='empty-dict'),
    pytest.param({'error': {'code': 'notSupported'}}, id='error-only'),
    pytest.param({'value': None}, id='value-is-none'),
    pytest.param({'value': 'not-a-list'}, id='value-is-a-string'),
    pytest.param('not-a-dict', id='body-is-a-string'),
])
def test_entries_of_is_total(body):
    assert entries_of(body) == []


def test_collect_pages_over_a_body_with_no_entry_list_returns_nothing():
    fetch = ScriptedFetch()
    assert collect_pages({'error': {'code': 'itemNotFound'}},
                         fetch, _identity) == []
    assert fetch.calls == []


# ---------------------------------------------------------------------------
# The change token (BROWSE-02's envelope contract)
# ---------------------------------------------------------------------------

def test_the_delta_link_is_copied_under_the_key_change_token():
    """CONSTRUCTED.

    No committed fixture carries `@odata.deltaLink` -- checked across all three
    business page fixtures and the rest of the set -- so the body for this one
    assertion is built here.

    Asserted by NAME rather than by "something was copied":
    Provider.persist_change_token and OneDrive.changes both read
    extra_info['change_token'], so a renamed key would break the change-token
    path with nothing to catch it.
    """
    body = {'value': [{'id': 'a'}], '@odata.deltaLink': 'https://delta/link'}
    extra_info = {}
    collect_pages(body, ScriptedFetch(), _identity, extra_info=extra_info)
    assert extra_info == {'change_token': 'https://delta/link'}, (
        'the key is a contract read by two callers, not a label')


def test_no_delta_link_leaves_extra_info_untouched(pages):
    extra_info = {}
    fetch = ScriptedFetch(pages[1], pages[2])
    collect_pages(pages[0], fetch, _identity, extra_info=extra_info)
    assert extra_info == {}, (
        'none of the three recorded pages carries a delta link; inventing one '
        'would make the change-token path look exercised when it is not')


def test_a_non_dict_extra_info_is_ignored():
    body = {'value': [], '@odata.deltaLink': 'https://delta/link'}
    collect_pages(body, ScriptedFetch(), _identity, extra_info=None)
    collect_pages(body, ScriptedFetch(), _identity, extra_info='not-a-dict')


# ---------------------------------------------------------------------------
# The depth stress (BROWSE-02, ROADMAP phase 2 criterion 3)
# ---------------------------------------------------------------------------
#
# WHERE 1,500 COMES FROM, so the number is not read as round. The shipped
# recursive shape was measured on CPython 3.11 with sys.getrecursionlimit() == 1000:
#
#     pages  result
#     -----  ---------------------------------------------
#       500  500 items
#       900  900 items
#      1000  RecursionError after 998 pages fetched
#      1500  RecursionError after 998 pages fetched
#
# Under Kodi the ceiling is LOWER, because the invoker, entrypoint.py, route(),
# _list_folder and get_folder_items are all already on the stack beneath the
# pager. So 1,500 is comfortably past the real limit rather than a safety margin.
#
# Re-measured while writing this, against a transcription of the shipped
# recursive shape and the same generated pages: 500 and 900 returned every item,
# 1,000 and 1,500 both raised RecursionError, and collect_pages returned every
# item at all four sizes. The fetch tally came out at 999 rather than 998 -- a
# counting-convention difference (the link is recorded before the call, so the
# fetch that raised is on the record), not a disagreement about where it dies.
# Noted so nobody later reads the two numbers as a regression.
#
# ONE ENTRY PER PAGE, deliberately. This isolates stack depth from list size,
# which is the property BROWSE-02 is actually about. Termination is a different
# property and is proven separately, against the three recorded pages above.
#
# NOTHING IS COMMITTED. Building these takes about 0.05 s; the same pages with
# fifty entries each would be 1.5 MB serialised, and a committed fixture that
# large would be paying storage to assert a property about the interpreter.
#
# WHAT THIS DOES NOT PROVE: memory behaviour on a 1-2 GB Android box. Both the
# recursive and the iterative shapes buffer every item, because the return value
# is a list, so this stress passes either way once the recursion is gone.
# BROWSE-02 is not evidence of streaming. The per-page escape hatch is on_page,
# and using it to render without buffering the folder is a later phase's work.

DEPTH_PAGES = 1500


def _generated_pages(count):
    """`count` page bodies of one entry each, chained by next link.

    Returned as (first_body, fetch) where fetch serves the rest from a dict.
    """
    bodies = {}
    first = None
    for index in range(count):
        link = 'https://graph.invalid/page/%d' % index
        body = {'value': [{'id': 'entry-%d' % index}]}
        if index + 1 < count:
            body['@odata.nextLink'] = 'https://graph.invalid/page/%d' % (index + 1)
        if index == 0:
            first = body
        else:
            bodies[link] = body

    calls = []

    def fetch(link):
        calls.append(link)
        return bodies[link]

    return first, fetch, calls


def test_fifteen_hundred_pages_yield_every_item_without_a_recursion_error():
    first, fetch, calls = _generated_pages(DEPTH_PAGES)
    items = collect_pages(first, fetch, _identity)

    assert len(items) == DEPTH_PAGES, (
        'the ROADMAP names 1,500 pages, and the shipped recursive shape raised '
        'RecursionError after fetching 998 of them')
    assert len(calls) == DEPTH_PAGES - 1, (
        'one fetch per page after the first, each exactly once: 1,499 for 1,500 '
        'pages')
    assert items[0]['id'] == 'entry-0'
    assert items[-1]['id'] == 'entry-%d' % (DEPTH_PAGES - 1), (
        'order must hold at depth as well as at three pages')


def test_cancelling_at_page_750_returns_an_empty_list():
    """The boundary check must still run at depth, not only near the start."""
    first, fetch, calls = _generated_pages(DEPTH_PAGES)
    items = collect_pages(first, fetch, _identity,
                          cancelled=CancelAfter(750))

    assert items == [], (
        'a cancel deep into a large folder is the case this matters most for: '
        'it is the folder slow enough that the user reached for the remote')
    assert len(calls) == 750, (
        'the run must stop fetching at the boundary it was cancelled on, not '
        'carry on to the end of the folder')
