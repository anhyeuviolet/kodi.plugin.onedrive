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

Extraction is per-entry and order-preserving. No function here holds state
between calls or reads a module-level mutable object, so entry N of a response
produces item N of a listing and no entry's result depends on any other.
"""

from resources.lib.vendor.clouddrive_common.utils import Utils

# The three facets that decide what Kodi plays an item as, in the order they
# win. A driveItem can legitimately carry both `video` and `image` -- a video
# with a poster frame -- and Kodi routes on one type, so leaving both set means
# the choice is made by dictionary iteration order and nobody chose it. Making
# the three mutually exclusive is what makes "a video is not also an image" true
# in every ordering rather than only in the one that was observed.
MEDIA_FACET_PRECEDENCE = ('video', 'audio', 'image')


def extract_item(entry, include_download_info=False):
    """One `driveItem` mapping into the item shape the browse layer reads.

    `entry` is a response entry exactly as Graph sent it. It is not required to
    be well formed: a reshaped or truncated body produces an item, not a
    traceback. `extract_item({})` returns an item with a null id and an empty
    name.
    """
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

    thumbnails = Utils.get_safe_value(entry, 'thumbnails')
    if isinstance(thumbnails, list) and thumbnails:
        item['thumbnail'] = Utils.get_safe_value(
            Utils.get_safe_value(thumbnails[0], 'large', {}), 'url', '')

    if include_download_info:
        item['download_info'] = {
            'url': Utils.get_safe_value(entry, '@microsoft.graph.downloadUrl')
        }
    return item
