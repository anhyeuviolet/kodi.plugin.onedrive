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
"""One action must not change what the next action asks for.

WHAT WAS MEASURED, and why this file is worth more than an assertion about an
attribute. `search()` wrote `filter=file ne null` into a dictionary the provider
held as a class attribute and passed to every request. A folder listing carrying
that leaked filter was measured to return **HTTP 400 notSupported**, in both the
unprefixed and the OData spelling, and the same listing without it returned 121
entries. So the consequence was not a subtly wrong listing -- after one search, a
folder listing was refused outright and the television showed an error where a
folder should be.

HOW LONG THE LEAK LASTS, settled from Kodi's own source rather than from the
device. `reuselanguageinvoker` defaults to false and `addon.xml` does not declare
it, so `sys.modules` is cold per invocation and today's exposure is one plugin
invocation wide. But `resources/lib/addon.py` holds `_provider = OneDrive()` as a
**class** attribute, so every action inside one invocation shares the instance --
which is why converting the parameter dictionary to an instance attribute would
have closed nothing. And `service.py` hands the `OneDrive` class to five services
that share one interpreter for a whole Kodi session, so the exposure exists
structurally there too; none of them calls `search()` today, so it is not
reachable, and that observation is 02-07's to close on the device.

The tests here are written to hold under BOTH interpreter lifetimes, which is why
there are two shapes rather than one:

  * the SEQUENCE test drives one instance through list, search, list -- the
    sequence that produced the measured 400;
  * the SECOND-CONSTRUCTION test builds a fresh provider after a search and
    checks it too. That is the shape that survives `reuselanguageinvoker` being
    turned on.

NO GATE FORBIDS THE MANIFEST FLAG, and that is deliberate. A test asserting
`reuselanguageinvoker` is absent from `addon.xml` would only forbid turning it on,
and a later phase may legitimately want it for the startup cost it saves. The fix
is written so the flag is safe either way; forbidding it would trade a real fix
for a prohibition.
"""

import pytest

from kodistub import kodi_stubs

FILTER_SPELLINGS = ('filter', '$filter')


class RecordingPort(object):
    """Stands in for the provider's `get`, recording what was asked for.

    Answers every call with a single empty page, so the pager stops immediately
    and the assertions are about the REQUEST rather than about the response.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, path, parameters=None, **kwargs):
        self.calls.append(
            (path, None if parameters is None else dict(parameters)))
        return {'value': []}

    @property
    def parameter_maps(self):
        return [parameters for _path, parameters in self.calls]


def _provider(recorder_port):
    # The provider import is INSIDE the test body, never at module scope, and
    # every test opens kodi_stubs first. A module-scope import would defeat
    # _Restore.check, which removes the five fake Kodi modules and every
    # resources.* module imported while they were installed, and then asserts the
    # removal. An import at module scope would leave resources.lib.provider
    # bound to a tree that had been torn down.
    from resources.lib.provider.onedrive import OneDrive

    provider = OneDrive()
    provider.configure(None, 'drive-1')
    provider.get = recorder_port
    return provider


def _assert_no_filter(parameters, when):
    for spelling in FILTER_SPELLINGS:
        assert spelling not in parameters, (
            'the request made %s carries a %r parameter. A folder listing '
            'carrying it was measured to return HTTP 400 notSupported, so the '
            'television shows an error where a folder should be: %r'
            % (when, spelling, parameters))


def test_a_listing_after_a_search_asks_for_what_it_asked_before(tmp_path):
    """The sequence that produced the measured 400, through ONE instance."""
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.graph.params import listing_parameters  # noqa: F401

        port = RecordingPort()
        provider = _provider(port)

        provider.get_folder_items(path='/')
        before = port.parameter_maps[-1]

        provider.search('holiday')
        after_search = port.parameter_maps[-1]

        provider.get_folder_items(path='/')
        after = port.parameter_maps[-1]

        _assert_no_filter(before, 'before any search')
        _assert_no_filter(after_search, 'by the search itself')
        _assert_no_filter(after, 'by the listing that followed a search')

        assert after == before, (
            'the listing after a search asked for something different from the '
            'listing before it: %r then %r. One action changed what the next '
            'action requested, which is the defect' % (before, after))


def test_a_provider_built_after_a_search_sees_clean_parameters(tmp_path):
    """The shape that survives reuselanguageinvoker being turned on.

    Two providers sharing nothing but a class. If any state lived on the class,
    the second would inherit what the first's search wrote.
    """
    with kodi_stubs(tmp_path / 'profile'):
        first_port = RecordingPort()
        first = _provider(first_port)
        first.search('holiday')

        second_port = RecordingPort()
        second = _provider(second_port)
        second.get_folder_items(path='/')

        listing = second_port.parameter_maps[-1]
        _assert_no_filter(listing, 'by a second provider built after a search')
        assert listing == {'expand': 'thumbnails'}, (
            'a freshly constructed provider inherited request state from an '
            'earlier one through their shared class: %r' % (listing,))


def test_ten_consecutive_listings_ask_for_the_same_thing(tmp_path):
    with kodi_stubs(tmp_path / 'profile'):
        port = RecordingPort()
        provider = _provider(port)

        for _ in range(10):
            provider.get_folder_items(path='/')

        maps = port.parameter_maps
        assert len(maps) == 10
        assert all(m == maps[0] for m in maps), (
            'ten identical calls produced different requests: %r' % (maps,))
        for index, mapping in enumerate(maps):
            _assert_no_filter(mapping, 'by listing %d of ten' % (index + 1))


def test_the_provider_holds_no_shared_mutable_parameter_object(tmp_path):
    """No class attribute, and no instance attribute either.

    Scoping it down to an instance would have closed nothing: addon.py holds one
    provider as a class attribute of its own, so every action in an invocation
    shares the instance.
    """
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive

        assert not hasattr(OneDrive, '_extra_parameters'), (
            'the shared class-level parameter dictionary is back')

        provider = _provider(RecordingPort())
        provider.search('holiday')
        assert not hasattr(provider, '_extra_parameters'), (
            'a per-instance parameter dictionary is not enough, and one exists')

        dictionaries = [
            value for name, value in vars(provider).items()
            if isinstance(value, dict) and any(
                spelling in value for spelling in FILTER_SPELLINGS)]
        assert dictionaries == [], (
            'the provider is carrying a mapping with a filter in it: %r'
            % (dictionaries,))


def test_a_mutated_parameter_mapping_does_not_reach_the_next_request(tmp_path):
    """The caller receives an object it may mutate. A shared one was mutated."""
    with kodi_stubs(tmp_path / 'profile'):
        port = RecordingPort()
        provider = _provider(port)

        provider.get_folder_items(path='/')
        port.calls[-1][1]['filter'] = 'file ne null'

        provider.get_folder_items(path='/')
        _assert_no_filter(port.parameter_maps[-1],
                          'after a caller mutated an earlier mapping')


@pytest.mark.parametrize('spelling', FILTER_SPELLINGS)
def test_no_request_any_entry_point_makes_carries_a_filter(tmp_path, spelling):
    """Every request site, not only the listing ones."""
    with kodi_stubs(tmp_path / 'profile'):
        port = RecordingPort()
        provider = _provider(port)

        provider.get_folder_items(path='/')
        provider.get_folder_items(item_id='item-1')
        provider.search('holiday')
        provider.search('holiday', item_id='item-1')
        provider.get_item(item_id='item-1')
        provider.get_item(path='/')

        assert len(port.calls) >= 6
        for path, parameters in port.calls:
            assert spelling not in (parameters or {}), (
                '%r carries a %r parameter' % (path, spelling))
            assert spelling not in path, (
                '%r names %r in the path itself' % (path, spelling))
