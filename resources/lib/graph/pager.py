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
"""Following a Graph paging link until it runs out, in a loop.

WHY A LOOP RATHER THAN RECURSION, with the measurement. The shipped shape called
itself once per page. Measured on CPython 3.11 with the default recursion limit
of 1000: it returned every item at 500 pages and at 900, and at both 1,000 and
1,500 pages it raised `RecursionError` after fetching 998. Under Kodi the ceiling
is lower still, because the invoker, `entrypoint.py`, the route table and
`get_folder_items` are all already on the stack beneath it. So a folder large
enough is not slow, it is a traceback.

WHAT ITERATING DOES NOT FIX, stated here so it is not claimed later. The whole
folder is still accumulated in memory before it is returned, because the return
value is a list. The recursive shape did that too, so the depth stress passes
either way once the recursion is gone, and this module is NOT evidence of
streaming. The per-page escape hatch is `on_page`, and using it to render a page
at a time without buffering the folder is a later phase's work.

Nothing here imports a Kodi module, and nothing here imports the item extractor
either. The extractor arrives as an argument, deliberately: this module's contract
is paging, cancellation and the shape of the envelope, and what an entry *becomes*
is the caller's business. Keeping it out is what stops a paging loop growing a
reason to know about facets, and lets each module be tested alone.
"""


def entries_of(body):
    """The entry list from a response envelope, or an empty list.

    Reading the key unconditionally is what turns an error body into a traceback
    instead of an empty listing, and error bodies are not hypothetical here.
    Three are committed in the fixture set, each carrying an `error` key and no
    entry list at all:

      * the 400 `notSupported`, from a filter leaking onto a listing;
      * the 404 `itemNotFound`, from a path that does not resolve;
      * the 501 `notSupported`, from the unsupported filter on the search
        endpoint.

    A non-list value is treated the same way as a missing one. The point is that
    the caller receives something it can iterate, in every case.
    """
    if not isinstance(body, dict):
        return []
    entries = body.get('value')
    if not isinstance(entries, list):
        return []
    return entries


def collect_pages(body, fetch, extract, cancelled=None, on_page=None,
                  on_before_add_item=None, extra_info=None):
    """Every item across a paged response, in page order then entry order.

    `body` is the first page, already fetched. `fetch(link)` returns the next
    page for a paging link. `extract(entry)` turns one entry into one item.
    `cancelled()` is consulted at **every** page boundary. `on_page(items)`, when
    given, is called with each page's items as that page completes -- it is the
    hook a caller uses to render progressively instead of waiting for the whole
    folder. `on_before_add_item(item)` is called per item before it is kept.

    CANCELLATION RETURNS AN EMPTY LIST, and discards whatever was accumulated.
    Not a partial listing: the user cancelled because the listing was taking too
    long, and half a folder rendered as though it were the whole folder is a
    wrong answer presented as a right one, which the user cannot tell from a
    right one. The check runs at every boundary rather than only the first,
    because a cancel becoming true between any two consecutive pages is the same
    event.

    The shipped recursion got this wrong in a worse way than "returns a partial
    listing". Its inner frame returned `None` on cancellation and its outer frame
    then ran `items.extend(None)`, so a cancel between two pages was a
    `TypeError` raised inside the provider -- a failed listing carrying a
    traceback, not a short one.

    `@odata.deltaLink`, when the response carries one and `extra_info` is a dict,
    is copied into it under the key `change_token`. That literal is not a choice:
    `Provider.persist_change_token` and `OneDrive.changes` both read
    `extra_info['change_token']`, so renaming it would break the change-token
    path with nothing to catch it.
    """
    items = []
    while True:
        # At the top of every iteration, so the first page is a boundary like any
        # other. Checking only before the *next* fetch would let a run that was
        # already cancelled return the first page's items whenever that page
        # happened to be the last one -- a partial answer whose size depends on
        # where the folder ended.
        if cancelled and cancelled():
            return []

        page_items = []
        for entry in entries_of(body):
            item = extract(entry)
            if on_before_add_item:
                on_before_add_item(item)
            page_items.append(item)
        items.extend(page_items)

        if on_page:
            on_page(page_items)

        if isinstance(extra_info, dict) and isinstance(body, dict):
            delta_link = body.get('@odata.deltaLink')
            if delta_link:
                # The key name is read by Provider.persist_change_token and by
                # OneDrive.changes. It is a contract, not a label.
                extra_info['change_token'] = delta_link

        next_link = body.get('@odata.nextLink') if isinstance(body, dict) else None
        if not next_link:
            return items
        body = fetch(next_link)
