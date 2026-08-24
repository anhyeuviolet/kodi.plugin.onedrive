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
"""The query parameters each Graph request carries, built fresh every time.

WHY THIS IS A MODULE AND NOT A CONSTANT. The provider used to hold one dictionary
as a class attribute and pass it to every request. `search()` wrote a filter into
it. Graph answers 501 on a business drive because that filter is not among the
parameters the search endpoint documents -- and then the *next* folder listing
carried the same filter and answered 400. So after one search, browsing stopped
working: not quietly wrong, refused outright.

Scoping the dictionary down to an instance attribute would have closed nothing.
`resources/lib/addon.py` holds `_provider = OneDrive()` as a **class** attribute
of its own, so there is one instance per interpreter shared by every action in an
invocation, and `service.py` hands the class itself to five services that share
one interpreter for the whole Kodi session. Today the exposure is one invocation
wide, because `reuselanguageinvoker` defaults to false and `addon.xml` does not
declare it -- but that is one manifest line from being session-long, for good
performance reasons a later phase may well want.

So there is no shared mutable object here at all. Every function returns a new
dictionary, because an object a caller receives is an object a caller may mutate,
and a shared one did.

Nothing here imports a Kodi module, and nothing here imports the rest of the
add-on.
"""

# The expand parameter's value, and the spelling is the measured one rather than
# the documented one. The provider builds its query with urlencode, so this
# arrives as `expand=thumbnails` with no leading `$`. Both spellings were
# measured against a live drive and returned identical listings, with the
# thumbnails key present on every entry -- Graph honours the unprefixed form.
#
# That measurement is also why the filter this module exists to remove was a real
# defect rather than an inert string: an unprefixed parameter Graph ignored could
# not have produced the recorded 501 and 400. It did, so it was live.
EXPAND_THUMBNAILS = 'thumbnails'


def listing_parameters():
    """A fresh mapping for a folder-listing request, new on every call.

    New rather than shared, because the caller receives an object it may mutate
    and a shared one was mutated -- by `search()`, into the state that broke the
    next listing.
    """
    return {'expand': EXPAND_THUMBNAILS}


def search_parameters():
    """A fresh mapping for a search request, new on every call.

    Carries the expand parameter and nothing else. In particular no filter, under
    either spelling: `$filter` is not among the parameters Graph documents for the
    search endpoint -- the documented set is `$expand`, `$select`, `$skipToken`,
    `$top` and `$orderby` -- so the 501 `notSupported` was the service enforcing
    its own documented surface, not a bug and not a tenant quirk. There is no
    server-side spelling that works, so the classification happens on the client.

    The cost, stated rather than hidden: a search now retrieves folders as well
    as files and the client discards the rows it paid to receive.
    """
    return {'expand': EXPAND_THUMBNAILS}
