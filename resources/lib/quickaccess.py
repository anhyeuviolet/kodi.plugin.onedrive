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
"""The decisions behind quick access, kept apart from the Kodi calls that act on them.

Three questions are answered here, each without importing a Kodi module so the
answers can be tested on a host with no Kodi installed:

  * which drive the add-on may open straight away, skipping the account list;
  * which folder a drive opens on (the "start folder"), stored per drive and per
    content type in a small JSON file in the profile;
  * whether a folder may be added to the Kodi library as a quick export, and
    the export record that does it.

The library question has one answer that matters more than the rest: the export
service empties an existing destination folder before it writes a new export
there when the `clean_folder` setting is on, and that setting is on by default.
A quick export therefore refuses any destination folder that already exists on
disk or that another export already writes into. It never deletes anything that
is not its own.
"""

import json
import os
import re

START_FOLDERS_FILE = 'start_folders.json'

LIBRARY_KINDS = ('movies', 'tvshows')

# Where a folder of several TV shows goes. Kodi reads each folder directly
# inside a TV source as one show, so such a folder is a source of its own
# (library/tvcollections/<name>/) rather than one more show under tvshows/.
TV_COLLECTIONS = 'tvcollections'
DESTINATION_KINDS = LIBRARY_KINDS + (TV_COLLECTIONS,)

# Why a plan was refused. The add-on maps each one to a sentence; the plan never
# carries words of its own.
ALREADY_EXPORTED = 'already_exported'
NAME_TAKEN = 'name_taken'
FOLDER_EXISTS = 'folder_exists'
UNKNOWN_KIND = 'unknown_kind'
INVALID_NAME = 'invalid_name'


def single_drive(accounts, needs_reauth=None):
    """The one drive to open directly, or None.

    Only when there is exactly one account holding exactly one drive, and that
    account is not waiting to be signed in again. A stale account must keep its
    own row, because that row is what starts the new sign-in. Two or more
    accounts keep the list, because choosing between them is the list's job.
    """
    if not isinstance(accounts, dict) or len(accounts) != 1:
        return None
    account = list(accounts.values())[0]
    if not isinstance(account, dict):
        return None
    if needs_reauth and needs_reauth(account):
        return None
    drives = account.get('drives')
    if not isinstance(drives, list) or len(drives) != 1:
        return None
    drive = drives[0]
    if not isinstance(drive, dict) or not drive.get('id'):
        return None
    return drive


# ---------------------------------------------------------------------------
# Start folders
# ---------------------------------------------------------------------------

def _start_folders_path(profile_path):
    return os.path.join(profile_path, START_FOLDERS_FILE)


def load_start_folders(profile_path):
    """Everything stored, or an empty dict.

    An absent, unreadable or malformed file is an empty store rather than a
    failure. The worst outcome of losing it is that the drive opens on its root
    folder, which is the behaviour before this feature existed.
    """
    try:
        with open(_start_folders_path(profile_path), 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_start_folders(profile_path, data):
    # Written to a sibling file and moved into place, so a crash halfway through
    # leaves the previous store intact instead of half a JSON document.
    if not os.path.isdir(profile_path):
        os.makedirs(profile_path)
    path = _start_folders_path(profile_path)
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(temporary, path)


def get_start_folder(profile_path, driveid, content_type):
    """The stored start folder, or None when there is none or it is unusable."""
    drive = load_start_folders(profile_path).get(driveid)
    if not isinstance(drive, dict):
        return None
    folder = drive.get(content_type)
    if not isinstance(folder, dict):
        return None
    if not folder.get('item_id') or not folder.get('item_driveid'):
        return None
    return {'item_id': str(folder['item_id']),
            'item_driveid': str(folder['item_driveid']),
            'name': str(folder.get('name') or '')}


def set_start_folder(profile_path, driveid, content_type, item_driveid,
                     item_id, name):
    data = load_start_folders(profile_path)
    drive = data.get(driveid)
    if not isinstance(drive, dict):
        drive = {}
    drive[content_type] = {'item_driveid': item_driveid, 'item_id': item_id,
                           'name': name or ''}
    data[driveid] = drive
    _save_start_folders(profile_path, data)


def clear_start_folder(profile_path, driveid, content_type):
    """Forget the start folder. Returns whether one was stored."""
    data = load_start_folders(profile_path)
    drive = data.get(driveid)
    if not isinstance(drive, dict) or content_type not in drive:
        return False
    del drive[content_type]
    if drive:
        data[driveid] = drive
    else:
        del data[driveid]
    _save_start_folders(profile_path, data)
    return True


# ---------------------------------------------------------------------------
# Library (quick export)
# ---------------------------------------------------------------------------

def library_destination(library_root, kind):
    """The folder a quick export of `kind` writes into.

    Movies and TV shows go into separate folders because Kodi assigns the
    scraper to a source, not to a file: each folder is added once as a source
    with its own content type.
    """
    if kind not in DESTINATION_KINDS:
        raise ValueError('unknown library kind: %r' % (kind,))
    return os.path.join(library_root, kind)


def valid_folder_name(name):
    """Whether `name` names one folder directly inside the library folder.

    OneDrive itself refuses both separators in a name, so a name that carries
    one did not come from OneDrive. Refused anyway: the name is joined onto a
    path, and removing an export may delete that path.
    """
    if not isinstance(name, str) or not name.strip():
        return False
    if name in ('.', '..') or '/' in name or '\\' in name or '\0' in name:
        return False
    return True


def _same_path(a, b):
    return (os.path.normcase(os.path.normpath(a or ''))
            == os.path.normcase(os.path.normpath(b or '')))


def plan_library_export(exports, library_root, kind, driveid, item_driveid,
                        item_id, name, exists):
    """(export, None) when the folder can be exported, else (None, reason).

    `exports` is the export store's current contents, keyed by item id.
    `exists(path)` answers whether a path exists on disk; it is injected so this
    stays free of Kodi's file functions.
    """
    if kind not in DESTINATION_KINDS:
        return None, UNKNOWN_KIND
    if not valid_folder_name(name):
        return None, INVALID_NAME
    exports = exports if isinstance(exports, dict) else {}
    if item_id in exports:
        return None, ALREADY_EXPORTED
    destination = library_destination(library_root, kind)
    folded = (name or '').casefold()
    for other in exports.values():
        if not isinstance(other, dict):
            continue
        if (_same_path(other.get('destination_folder'), destination)
                and str(other.get('name') or '').casefold() == folded):
            return None, NAME_TAKEN
    if exists(os.path.join(destination, name)):
        return None, FOLDER_EXISTS
    export = {
        'id': item_id,
        'item_driveid': item_driveid,
        'driveid': driveid,
        'name': name,
        'content_type': 'video',
        'destination_folder': destination,
        # Follow later changes on the drive and rescan the library after each
        # one, so a new episode appears without anybody opening the add-on.
        'watch': True,
        'update_library': True,
        # .nfo and artwork kept beside the videos help the scraper; they are
        # small, and nothing else is downloaded.
        'download_artwork': True,
        'schedule': False,
        'schedules': [],
        'run_immediately': True,
    }
    return export, None


# ---------------------------------------------------------------------------
# Latest videos
# ---------------------------------------------------------------------------

# How far below the chosen folder to look, and how many folder listings one
# request may cost. A series folder keeps its episodes one or two levels down;
# the listing cap is what keeps a widget on the home screen from walking a
# whole drive every time it is drawn.
LATEST_MAX_DEPTH = 2
LATEST_MAX_LISTINGS = 25
LATEST_LIMIT = 50


def newest_videos(list_children, root, is_video, max_depth=LATEST_MAX_DEPTH,
                  max_listings=LATEST_MAX_LISTINGS, limit=LATEST_LIMIT):
    """The newest videos under `root`, newest first, at most `limit` of them.

    list_children(folder) -> the items of one folder, `folder` being `root` or
    an item that list returned. Folders are walked breadth first, so when the
    listing cap is reached it is the deepest folders that are left out.

    Items are ordered by `last_modified_date`, which Graph sends as an ISO 8601
    UTC timestamp, so comparing the strings compares the times. An item with no
    date sorts last rather than failing the listing.
    """
    videos = []
    queue = [(root, 0)]
    listings = 0
    while queue and listings < max_listings:
        folder, depth = queue.pop(0)
        listings += 1
        for item in list_children(folder) or []:
            if not isinstance(item, dict):
                continue
            if 'folder' in item:
                if depth < max_depth:
                    queue.append((item, depth + 1))
            elif is_video(item):
                videos.append(item)
    videos.sort(key=lambda item: str(item.get('last_modified_date') or ''),
                reverse=True)
    return videos[:limit]


# ---------------------------------------------------------------------------
# Folder listing cache
# ---------------------------------------------------------------------------

# Listings that change on their own and are cheap to wrong: never cached.
UNCACHED_PATHS = ('recent', 'sharedWithMe')


def listing_cache_key(driveid, item_driveid, item_id, path, variant):
    """The key a folder listing is cached under, or None for one never cached.

    `variant` carries anything that changes what an item looks like -- the
    thumbnail size -- so changing the setting cannot serve rows built the old
    way.
    """
    if not item_id and (not path or path in UNCACHED_PATHS):
        return None
    return json.dumps([driveid, item_driveid or '', item_id or '', path or '',
                       variant], separators=(',', ':'))


# ---------------------------------------------------------------------------
# Collections: Favourites and playlists made from a folder
# ---------------------------------------------------------------------------

# A folder's videos, walked deeper than Latest videos: a playlist of a series
# wants every episode, not the newest fifty. Still bounded, because each
# listing is a request and the user is waiting on a busy dialog.
COLLECT_MAX_DEPTH = 4
COLLECT_MAX_LISTINGS = 100
FAVOURITES_LIMIT = 200
PLAYLIST_LIMIT = 2000

_DIGITS = re.compile(r'(\d+)')


def natural_key(name):
    """Episode 2 before Episode 10, whatever the case."""
    return [(0, int(part), '') if part.isdigit() else (1, 0, part.casefold())
            for part in _DIGITS.split(name or '') if part]


def collect_videos(list_children, root, is_video, max_depth=COLLECT_MAX_DEPTH,
                   max_listings=COLLECT_MAX_LISTINGS, limit=None):
    """Every video under `root`, in the order a person would watch them.

    Returns (videos, complete). Each video is (folders, item): `folders` is the
    list of folder names from `root` down to the one holding it. Ordered by
    folder path and then by name, both naturally (2 before 10). `complete` is
    False when a cap cut the walk short, so the caller can say so.
    """
    found = []
    queue = [(root, [], 0)]
    listings = 0
    complete = True
    while queue:
        if listings >= max_listings:
            complete = False
            break
        folder, names, depth = queue.pop(0)
        listings += 1
        for item in list_children(folder) or []:
            if not isinstance(item, dict):
                continue
            if 'folder' in item:
                if depth < max_depth:
                    queue.append((item, names + [str(item.get('name') or '')],
                                  depth + 1))
                else:
                    complete = False
            elif is_video(item):
                found.append((names, item))
    found.sort(key=lambda entry: ([natural_key(n) for n in entry[0]],
                                  natural_key(str(entry[1].get('name') or ''))))
    if limit is not None and len(found) > limit:
        found = found[:limit]
        complete = False
    return found, complete


def video_label(folders, name):
    """What a Favourites row or playlist entry is called.

    The file name without its extension, after the folder holding it when that
    is not the chosen folder itself -- "Season 1 - Episode 01" rather than
    twelve rows all called "Episode 01".
    """
    stem = name.rsplit('.', 1)[0] if '.' in (name or '')[1:] else (name or '')
    return '%s - %s' % (folders[-1], stem) if folders else stem


def favourites_to_add(existing_paths, candidates):
    """The candidates whose path is not a favourite yet, in order, once each.

    Kodi's AddFavourite removes a favourite that is already there, so adding
    one twice would take it away again.
    """
    seen = set(existing_paths or ())
    result = []
    for candidate in candidates:
        if candidate['path'] in seen:
            continue
        seen.add(candidate['path'])
        result.append(candidate)
    return result


_UNSAFE_FILE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def playlist_filename(name):
    """A file name for the playlist of the folder `name`, safe on every OS."""
    cleaned = _UNSAFE_FILE_CHARS.sub(' ', name or '').strip(' .')
    cleaned = re.sub(r'\s+', ' ', cleaned)[:80] or 'OneDrive'
    return 'OneDrive - %s.m3u' % cleaned


def m3u_playlist(entries):
    """An extended M3U playlist of (label, url) entries, as text."""
    lines = ['#EXTM3U']
    for label, url in entries:
        label = re.sub(r'[\r\n]+', ' ', label or '')
        lines.append('#EXTINF:-1,%s' % label)
        lines.append(url)
    return '\n'.join(lines) + '\n'
