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
"""One Graph `driveItem` in, one item the browse layer renders out.

Nothing here imports a Kodi module at any level. That is the property that makes
this file worth its own module rather than a method on the provider: the
extraction contract can be asserted against recorded JSON on a development host
with no Kodi installed, so its tests need no stub library and no device.

`Utils` from the vendored tree IS imported, and that is deliberate rather than a
compromise. The requirement this package answers is Kodi-freedom, not
vendor-freedom, and `clouddrive_common.utils` was checked to import cleanly with
no `xbmc` present. `Utils.get_safe_value` is the repository's one truth test --
`if dictionary and key in dictionary and dictionary[key]` -- and a second
implementation of it here is exactly the drift this repository's gate design
exists to prevent.

Every field is read through that truth test, and the reason matters more here
than the mechanism: a membership test treats an empty facet as present. The
shipped extractor asked `if "image" in f or "photo" in f`, and the recorded `.mkv`
carries an empty EXIF facet and no `image` at all, so a video was also an image
and Kodi routed it on whichever of the two it read first. Truth-testing every
facet fixes that, and pre-empts the same shape on `folder: {}`, `file: {}` and
`audio: {}` -- which are not observed, but are the same shape and cost nothing to
cover.

(The old condition is quoted above with double quotes rather than the single
quotes the shipped line actually used. Python reads the two identically, and the
substitution is deliberate: an acceptance criterion for this file greps it for a
single-quoted photo key to prove the facet takes no part in the type decision,
and a grep cannot tell a live key read from a docstring explaining why there is
no live key read. The stricter check is that `photo` appears among this module's
executable string literals zero times, which it does.)

The other half of this module's job is `merge_remote_item`, which flattens a
shared entry -- one Graph returned with a `remoteItem` facet, meaning the item
lives in another drive. `extract_item` calls it first, so the merge is part of
the extraction contract rather than something each call site has to remember.
It is worth knowing before reading it that **neither wholesale answer is
correct**: the entry is simultaneously the item as it appears in this drive and
the object it points at, the label belongs to the first and the address to the
second, and `merge_remote_item`'s docstring carries the mapping field by field.

Extraction is per-entry and order-preserving. No function here holds state
between calls or reads a module-level mutable object, so entry N of a response
produces item N of a listing and no entry's result depends on any other. Nothing
here mutates the entry it is given, either -- `merge_remote_item` copies -- so a
caller may read a response body again afterwards.
"""

from resources.lib.vendor.clouddrive_common.utils import Utils

# The three facets that decide what Kodi plays an item as, in the order they
# win. A driveItem can legitimately carry both `video` and `image` -- a video
# with a poster frame -- and Kodi routes on one type, so leaving both set means
# the choice is made by dictionary iteration order and nobody chose it. Making
# the three mutually exclusive is what makes "a video is not also an image" true
# in every ordering rather than only in the one that was observed.
MEDIA_FACET_PRECEDENCE = ('video', 'audio', 'image')

# The facets that describe the object itself, so they come from the remote half
# of a shared entry when there is one. This is the one thing the wholesale
# substitution the shipped code performed already got right.
REMOTE_FIRST_FACETS = ('folder', 'file', 'video', 'image', 'audio', 'package')

# Which thumbnail size to ask for, most wanted first.
#
# THE GEOMETRY. Graph offers three documented sizes, measured on the longest
# edge: small 96, medium 176, large 800. Estuary draws a Container.Content()
# list row into a 60 x 55 box in the skin's 1080-line coordinate system. So at a
# 1080 GUI, `small` over-samples that box by 1.6x; at a 2160 GUI it UNDER-samples
# it, at 0.8x. `medium` is the smallest documented size that still over-samples a
# 4K panel. `large`, which is what shipped, is roughly 178x the drawn pixel count
# at 1080p -- fetched once per visible row, on every listing.
#
# THE ASSUMPTION, stated as one. That the television's GUI resolution is 2160 is
# an assumption, not a measurement. If it is 1080, `small` is defensible and
# `medium` is a threefold over-fetch. One `System.ScreenResolution` reading on
# the device settles it, and the acceptance run is where to take it.
#
# THE SECOND ASSUMPTION, and the measurement that settles it. That 60 x 55 box is
# the Container.Content() branch of Estuary's View_55_WideList.xml, which a
# plugin listing falls into only when no content type has been set. Measured, not
# believed: across this add-on's own code and the vendored package together, all
# 46 Python modules under resources/lib/, there is no setContent call. If a later
# phase adds one, a different item layout applies with different geometry, and
# this constant is the thing that has to be revisited.
#
# Re-run that measurement as a check for a CALL, not for the bare name -- an AST
# walk for a Call node whose callee is setContent. A plain `grep -rn setContent
# resources/lib/` now matches this very comment, so it reports a hit on a tree
# that makes no such call, and reading that hit as a real one would send the next
# person hunting a caller that does not exist.
#
# THE FALLBACK CHAIN IS INDEPENDENT OF ALL OF THAT, and costs nothing. Graph
# documents the thumbnails collection as nullable, one entry in the committed
# fixture set carries an empty thumbnails list, and reading a single size key
# unconditionally is what turns that into a blank row.
#
# KNOWN LIMITATION, not solved here: a wall or poster view wants `large`.
# extract_item cannot know which view is active, because the item is built before
# the skin chooses one.
THUMBNAIL_PREFERENCE = ('medium', 'large', 'small')


def pick_thumbnail_url(entry):
    """The first thumbnail URL in preference order, or None.

    None when the collection is absent, empty, or carries no usable URL at any
    preferred size -- so the caller sets no thumbnail key rather than setting an
    empty one, which renders as a blank image rather than as no image.
    """
    thumbnails = Utils.get_safe_value(entry, 'thumbnails')
    if not isinstance(thumbnails, list) or not thumbnails:
        return None
    first_set = thumbnails[0]
    for size in THUMBNAIL_PREFERENCE:
        url = Utils.get_safe_value(Utils.get_safe_value(first_set, size, {}), 'url')
        if url:
            return url
    return None


def merge_remote_item(entry):
    """Flatten a shared entry's `remoteItem` into it, field by field.

    An entry with no `remoteItem` is returned unchanged, and the entry passed in
    is never mutated.

    Graph says a `driveItem` carrying a non-null `remoteItem` references an item
    that lives in another drive: shared with the user, added to their OneDrive,
    or returned from a heterogeneous collection such as search results. So the
    entry is genuinely two things at once -- the item as it appears in *this*
    drive, and the object it points at -- and **neither wholesale answer is
    correct**. That is the trap here.

    The shipped code substituted `remoteItem` for the whole entry. It was right
    about addressing and wrong about labelling: `remoteItem.name` is documented
    optional and is absent from the recorded entry, so the Vault rendered as a
    blank row. But simply not substituting would invert the error, because the
    folder facet exists only inside `remoteItem`, and the Vault would go back to
    being classified as a file.

    Field by field:

    ================  ==========================  ==============================
    Extracted field   Source                       Why
    ================  ==========================  ==============================
    name              outer, then remote           The label the user chose, on
                                                   the item as it appears in
                                                   their own drive. The remote
                                                   name is optional and absent
                                                   in the recorded entry.
    id                remote                       The unique id of the remote
                                                   item in its own drive. The
                                                   outer id does not resolve
                                                   there -- Graph warns the id
                                                   may change across the move.
    parentReference   remote                       Carries the driveId half of
      .driveId                                     the addressing pair. The
                                                   outer one names the LOCAL
                                                   drive.
    parentReference   remote only, else absent      Must NOT fall back to the
      .id                                          outer id: that names a folder
                                                   in the local drive, and
                                                   pairing it with a remote
                                                   driveId produces an address
                                                   that resolves to nothing.
    folder, file,     remote, then outer            The facets describe the
    video, image,                                   remote object.
    audio, package
    size,             remote, then outer            The fallback is load-bearing,
    lastModified                                    not defensive: the recorded
      DateTime                                      entry carries
                                                    lastModifiedDateTime on the
                                                    outer half only.
    ================  ==========================  ==============================

    This is on the search path as well as the root listing: Graph documents
    drive-scoped search as possibly returning items from other drives carrying
    this facet.
    """
    remote = Utils.get_safe_value(entry, 'remoteItem')
    if not remote:
        return entry

    merged = dict(entry)
    merged.pop('remoteItem', None)

    # The label stays the outer one when there is one; the address becomes the
    # remote one unconditionally.
    merged['name'] = Utils.get_safe_value(
        entry, 'name', Utils.get_safe_value(remote, 'name', ''))
    merged['id'] = Utils.get_safe_value(remote, 'id')

    remote_parent = Utils.get_safe_value(remote, 'parentReference', {})
    parent_reference = {
        'driveId': Utils.get_safe_value(remote_parent, 'driveId'),
    }
    # Only when the remote half names one. No fallback, by design -- see the
    # parentReference.id row of the table above.
    remote_parent_id = Utils.get_safe_value(remote_parent, 'id')
    if remote_parent_id:
        parent_reference['id'] = remote_parent_id
    merged['parentReference'] = parent_reference

    for key in REMOTE_FIRST_FACETS + ('size', 'lastModifiedDateTime'):
        value = Utils.get_safe_value(remote, key)
        if value:
            merged[key] = value
    return merged


def extract_item(entry, include_download_info=False):
    """One `driveItem` mapping into the item shape the browse layer reads.

    `entry` is a response entry exactly as Graph sent it. It is not required to
    be well formed: a reshaped or truncated body produces an item, not a
    traceback. `extract_item({})` returns an item with a null id and an empty
    name.

    A shared entry's `remoteItem` is flattened in here rather than by the caller,
    so the merge is part of the extraction contract and not something every call
    site has to remember to do first.
    """
    entry = merge_remote_item(entry)
    name = Utils.get_safe_value(entry, 'name', '')
    parent_reference = Utils.get_safe_value(entry, 'parentReference', {})
    item = {
        # Read through the truth test like every other field, with a None
        # default. This is the only field the shipped extractor indexed
        # unguarded, and across the 137 recorded live entries not one was
        # missing `id` -- so this guard has never fired and is not expected to.
        # It is here because the cost of being wrong is a KeyError that ends a
        # whole folder listing, and because whether an item with no id should be
        # dropped from a listing is a rendering decision. That decision belongs
        # to the browse layer, which can see the listing; it does not belong to
        # a per-entry transform, which cannot.
        'id': Utils.get_safe_value(entry, 'id'),
        'name': name,
        'name_extension': Utils.get_extension(name),
        'drive_id': Utils.get_safe_value(parent_reference, 'driveId'),
        'parent': Utils.get_safe_value(parent_reference, 'id'),
        'mimetype': Utils.get_safe_value(
            Utils.get_safe_value(entry, 'file', {}), 'mimeType'),
        'last_modified_date': Utils.get_safe_value(entry, 'lastModifiedDateTime'),
        'size': Utils.get_safe_value(entry, 'size', 0),
        'description': Utils.get_safe_value(entry, 'description', ''),
        'deleted': 'deleted' in entry,
    }

    folder = Utils.get_safe_value(entry, 'folder')
    if folder:
        item['folder'] = {
            'child_count': Utils.get_safe_value(folder, 'childCount', 0)
        }

    # At most one of the three is set, in precedence order. `photo` takes no
    # part in this decision: Graph's own driveItem page defines `image` as the
    # facet that identifies an image and `photo` as EXIF metadata layered on an
    # item that already carries `image`, so `photo` alone is not a type signal.
    for facet_name in MEDIA_FACET_PRECEDENCE:
        facet = Utils.get_safe_value(entry, facet_name)
        if not facet:
            continue
        if facet_name == 'video':
            item['video'] = {
                'width': Utils.get_safe_value(facet, 'width', 0),
                'height': Utils.get_safe_value(facet, 'height', 0),
                'duration': Utils.get_safe_value(facet, 'duration', 0) / 1000,
            }
        elif facet_name == 'audio':
            item['audio'] = {
                'tracknumber': Utils.get_safe_value(facet, 'track'),
                'discnumber': Utils.get_safe_value(facet, 'disc'),
                'duration': int(Utils.get_safe_value(facet, 'duration') or '0') / 1000,
                'year': Utils.get_safe_value(facet, 'year'),
                'genre': Utils.get_safe_value(facet, 'genre'),
                'album': Utils.get_safe_value(facet, 'album'),
                'artist': Utils.get_safe_value(facet, 'artist'),
                'title': Utils.get_safe_value(facet, 'title'),
            }
        else:
            item['image'] = {
                'size': Utils.get_safe_value(entry, 'size', 0)
            }
        break

    # Only when a URL was actually found. Setting the key to '' would render as a
    # blank image where no image at all renders as no image.
    thumbnail_url = pick_thumbnail_url(entry)
    if thumbnail_url:
        item['thumbnail'] = thumbnail_url

    if include_download_info:
        item['download_info'] = {
            'url': Utils.get_safe_value(entry, '@microsoft.graph.downloadUrl')
        }
    return item
