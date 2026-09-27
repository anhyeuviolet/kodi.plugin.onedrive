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
"""Make a library folder a Kodi video source, without the user doing it.

An exported folder of .strm files reaches Movies and TV shows only once Kodi
knows two things about it: that it is a video source, and what its content
is (movies or TV shows, and which scraper reads it). Kodi offers no add-on API
for either, so until now the add-on ended with instructions -- open Videos >
Files > Add videos, browse to a folder inside the add-on's data, set the
content -- which is where most people stopped.

Kodi keeps the two answers in two places, and this module writes both:

  * the scraper and content live in the video database's `path` table, which
    Kodi reads every time it scans. A row written here takes effect on the
    next scan, with no restart. Only the SQLite database is written; a shared
    MySQL/MariaDB library (advancedsettings.xml <videodatabase>) is left alone
    and the caller falls back to the instructions.
  * the source itself lives in sources.xml, which Kodi reads at start. It is
    what keeps "Clean library" from treating the items as orphans and what
    shows the folder under Videos > Files; an entry written here shows up
    after the next restart, and is added again if Kodi rewrites the file
    without it.

Nothing here imports a Kodi module: every path is passed in, so each branch
is tested against real files.
"""

import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET

# Kodi's own defaults for a movie source: look in every folder below, and take
# the title from the file name. A TV source reads each folder directly inside
# it as one show, so it is not recursive at that level.
MOVIES = 'movies'
TVSHOWS = 'tvshows'
SCAN_RECURSIVE = {MOVIES: 2147483647, TVSHOWS: 0}

# The scrapers Kodi ships, newest first. Used only when Kodi's own default
# cannot be read.
FALLBACK_SCRAPERS = {
    MOVIES: ('metadata.themoviedb.org.python', 'metadata.themoviedb.org',
             'metadata.local'),
    TVSHOWS: ('metadata.tvshows.themoviedb.org.python', 'metadata.tvdb.com',
              'metadata.local'),
}

_VIDEO_DB = re.compile(r'^MyVideos(\d+)\.db$')

# Outcomes of ensure_path_content.
ADDED = 'added'
UPDATED = 'updated'
PRESENT = 'present'
KEPT = 'kept'          # the user already chose a different content: theirs wins


def folder_path(path):
    """`path` with exactly one trailing separator, as Kodi stores a folder."""
    if path.startswith(('special://', 'smb://', 'nfs://')) or '/' in path and '\\' not in path:
        sep = '/'
    else:
        sep = os.sep
    return path.rstrip('/\\') + sep


def _same_folder(a, b):
    return folder_path(a or '').rstrip('/\\') == folder_path(b or '').rstrip('/\\')


# ---------------------------------------------------------------------------
# The video database
# ---------------------------------------------------------------------------

def uses_external_database(advancedsettings_path):
    """True when advancedsettings.xml moves the video library off SQLite."""
    if not advancedsettings_path or not os.path.isfile(advancedsettings_path):
        return False
    try:
        root = ET.parse(advancedsettings_path).getroot()
    except (ET.ParseError, OSError):
        # Unreadable: Kodi could not have read it either, but do not guess.
        return True
    node = root.find('videodatabase')
    if node is None:
        return False
    kind = (node.findtext('type') or '').strip().lower()
    return kind not in ('', 'sqlite3')


def find_video_database(database_dir):
    """The newest MyVideosNN.db in `database_dir`, or None."""
    try:
        names = os.listdir(database_dir)
    except OSError:
        return None
    best = None
    for name in names:
        match = _VIDEO_DB.match(name)
        if match and (best is None or int(match.group(1)) > best[0]):
            best = (int(match.group(1)), name)
    return os.path.join(database_dir, best[1]) if best else None


def ensure_path_content(db_path, path, content, scraper, now=None):
    """Give `path` a content and a scraper in the video database.

    Returns ADDED, UPDATED (the row existed without a content), PRESENT (it
    already has this content) or KEPT (it has another one, chosen by somebody
    in Kodi's own dialog, and that choice is left as it is). Raises
    sqlite3.Error when the database cannot be written.
    """
    path = folder_path(path)
    stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(path)')}
        if not {'strPath', 'strContent', 'strScraper'} <= columns:
            raise sqlite3.DatabaseError('not a Kodi video database: %s' % db_path)
        row = connection.execute(
            'SELECT idPath, strContent FROM path WHERE strPath = ?',
            (path,)).fetchone()
        values = {
            'strContent': content,
            'strScraper': scraper,
            'scanRecursive': SCAN_RECURSIVE[content],
            'useFolderNames': 0,
            'strSettings': '',
            'noUpdate': 0,
            'exclude': 0,
        }
        values = dict((k, v) for k, v in values.items() if k in columns)
        if row is None:
            values['strPath'] = path
            if 'dateAdded' in columns:
                values['dateAdded'] = stamp
            names = sorted(values)
            connection.execute(
                'INSERT INTO path (%s) VALUES (%s)'
                % (', '.join(names), ', '.join('?' * len(names))),
                [values[n] for n in names])
            outcome = ADDED
        elif row[1] == content:
            outcome = PRESENT
        elif row[1]:
            outcome = KEPT
        else:
            names = sorted(values)
            connection.execute(
                'UPDATE path SET %s WHERE idPath = ?'
                % ', '.join('%s = ?' % n for n in names),
                [values[n] for n in names] + [row[0]])
            outcome = UPDATED
        connection.commit()
        return outcome
    finally:
        connection.close()


def choose_scraper(content, kodi_default, installed):
    """Kodi's default scraper for `content` when set, else a shipped one.

    `installed(addon_id)` answers whether an add-on is installed and enabled.
    None when there is no scraper at all.
    """
    if kodi_default and installed(kodi_default):
        return kodi_default
    for addon_id in FALLBACK_SCRAPERS[content]:
        if installed(addon_id):
            return addon_id
    return None


# ---------------------------------------------------------------------------
# sources.xml
# ---------------------------------------------------------------------------

def ensure_video_source(sources_path, name, path):
    """Add `path` to the video sources in sources.xml, once.

    Returns True when the file was written, False when a video source for the
    folder was already there. The previous file is kept as sources.xml.bak on
    the first write, and the new one is written beside it and moved into place,
    so a power cut leaves either the old file or the new one.
    """
    path = folder_path(path)
    if os.path.isfile(sources_path):
        tree = ET.parse(sources_path)
        root = tree.getroot()
    else:
        root = ET.Element('sources')
        tree = ET.ElementTree(root)
    video = root.find('video')
    if video is None:
        video = ET.SubElement(root, 'video')
        ET.SubElement(video, 'default', {'pathversion': '1'})
    for source in video.findall('source'):
        for node in source.findall('path'):
            if _same_folder(node.text, path):
                return False
    names = {(s.findtext('name') or '').strip() for s in video.findall('source')}
    label, n = name, 2
    while label in names:
        label = '%s (%d)' % (name, n)
        n += 1
    source = ET.SubElement(video, 'source')
    ET.SubElement(source, 'name').text = label
    ET.SubElement(source, 'path', {'pathversion': '1'}).text = path
    ET.SubElement(source, 'allowsharing').text = 'true'
    _indent(root)
    backup = sources_path + '.bak'
    if os.path.isfile(sources_path) and not os.path.exists(backup):
        with open(sources_path, 'rb') as original, open(backup, 'wb') as copy:
            copy.write(original.read())
    temporary = sources_path + '.tmp'
    tree.write(temporary, encoding='utf-8', xml_declaration=True)
    os.replace(temporary, sources_path)
    return True


def _indent(element, level=0):
    pad = '\n' + '    ' * level
    if len(element):
        if not (element.text or '').strip():
            element.text = pad + '    '
        for child in element:
            _indent(child, level + 1)
        if not (child.tail or '').strip():
            child.tail = pad
    if level and not (element.tail or '').strip():
        element.tail = pad


# ---------------------------------------------------------------------------
# TV shows: one show, or a folder of shows
# ---------------------------------------------------------------------------

_SEASON = re.compile(
    r'^\s*(season|series|saison|staffel|temporada|stagione|seizoen|s|'
    r'mùa|phần|specials?|extras?)?\s*[\s._-]*\d{0,3}\s*$',
    re.IGNORECASE)


def looks_like_one_show(child_names, has_videos):
    """Whether a folder holds one TV show rather than several.

    One show when it has videos of its own, or when every folder in it is
    named like a season (Season 1, S02, Mua 3, Specials, 04). Several shows
    when it has only folders and at least one of them is named like anything
    else.
    """
    if has_videos or not child_names:
        return True
    return all(_SEASON.match(name or '') and any(c.isalnum() for c in name)
               for name in child_names)


# ---------------------------------------------------------------------------
# Remembering what was registered
# ---------------------------------------------------------------------------
#
# Kodi keeps its sources in memory and writes sources.xml from memory whenever
# somebody edits a source in its own dialogs. An entry written here while Kodi
# runs is therefore lost if the user adds a source of their own before the next
# restart. The add-on keeps its own list, and the service puts any missing
# entry back when Kodi starts.

REGISTRY_FILE = 'library_sources.json'


def remember_source(registry_path, name, path):
    import json
    entries = read_registry(registry_path)
    path = folder_path(path)
    if any(_same_folder(e.get('path'), path) for e in entries):
        return
    entries.append({'name': name, 'path': path})
    temporary = registry_path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as out:
        json.dump(entries, out, ensure_ascii=False, indent=1)
    os.replace(temporary, registry_path)


def read_registry(registry_path):
    import json
    try:
        with open(registry_path, encoding='utf-8') as source:
            entries = json.load(source)
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    return [e for e in entries
            if isinstance(e, dict) and isinstance(e.get('path'), str)
            and isinstance(e.get('name'), str)]


def restore_sources(registry_path, sources_path, folder_exists=os.path.isdir):
    """Put back every remembered source sources.xml has lost. The count."""
    restored = 0
    for entry in read_registry(registry_path):
        if not folder_exists(entry['path']):
            continue
        if ensure_video_source(sources_path, entry['name'], entry['path']):
            restored += 1
    return restored
