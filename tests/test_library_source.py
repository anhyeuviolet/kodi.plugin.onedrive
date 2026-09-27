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
"""A library folder becomes a Kodi video source without the user's help.

Driven against a real SQLite file with Kodi's `path` table and a real
sources.xml, because both are Kodi's files and the only thing worth asserting
is what ends up in them.
"""

import os
import sqlite3
import xml.etree.ElementTree as ET

import pytest

from kodistub import kodi_stubs
from resources.lib import library_source

# Kodi 21's path table, column for column.
PATH_TABLE = ('CREATE TABLE path ( idPath integer primary key, strPath text, '
              'strContent text, strScraper text, strHash text, '
              'scanRecursive integer, useFolderNames bool, strSettings text, '
              'noUpdate bool, exclude bool, allAudio bool, dateAdded text, '
              'idParentPath integer)')


def _video_db(folder, version=121):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'MyVideos%d.db' % version)
    connection = sqlite3.connect(path)
    connection.execute(PATH_TABLE)
    connection.commit()
    connection.close()
    return path


def _rows(db):
    connection = sqlite3.connect(db)
    try:
        return connection.execute(
            'SELECT strPath, strContent, strScraper, scanRecursive, exclude '
            'FROM path ORDER BY idPath').fetchall()
    finally:
        connection.close()


def _video_sources(sources_path):
    root = ET.parse(sources_path).getroot()
    return [(s.findtext('name'), s.findtext('path'))
            for s in root.find('video').findall('source')]


def test_a_folder_gets_its_content_and_scraper(tmp_path):
    db = _video_db(str(tmp_path / 'Database'))
    folder = str(tmp_path / 'library' / 'movies')

    outcome = library_source.ensure_path_content(
        db, folder, 'movies', 'metadata.themoviedb.org.python')

    assert outcome == library_source.ADDED
    assert _rows(db) == [(folder + os.sep, 'movies',
                          'metadata.themoviedb.org.python', 2147483647, 0)]


def test_registering_twice_changes_nothing(tmp_path):
    db = _video_db(str(tmp_path / 'Database'))
    folder = str(tmp_path / 'library' / 'tvshows') + os.sep
    library_source.ensure_path_content(db, folder, 'tvshows', 'scraper.tv')
    assert (library_source.ensure_path_content(db, folder, 'tvshows', 'scraper.tv')
            == library_source.PRESENT)
    assert len(_rows(db)) == 1
    assert _rows(db)[0][3] == 0, 'a TV source reads each folder in it as a show'


def test_a_content_the_user_chose_is_kept(tmp_path):
    db = _video_db(str(tmp_path / 'Database'))
    folder = str(tmp_path / 'library' / 'movies') + os.sep
    connection = sqlite3.connect(db)
    connection.execute("INSERT INTO path (strPath, strContent, strScraper) "
                       "VALUES (?, 'musicvideos', 'their.scraper')", (folder,))
    connection.commit()
    connection.close()

    assert (library_source.ensure_path_content(db, folder, 'movies', 'mine')
            == library_source.KEPT)
    assert _rows(db)[0][1:3] == ('musicvideos', 'their.scraper')


def test_a_row_kodi_made_without_a_content_is_filled_in(tmp_path):
    """Kodi adds a path row for every folder it has played from."""
    db = _video_db(str(tmp_path / 'Database'))
    folder = str(tmp_path / 'library' / 'movies') + os.sep
    connection = sqlite3.connect(db)
    connection.execute("INSERT INTO path (strPath) VALUES (?)", (folder,))
    connection.commit()
    connection.close()

    assert (library_source.ensure_path_content(db, folder, 'movies', 'mine')
            == library_source.UPDATED)
    assert _rows(db) == [(folder, 'movies', 'mine', 2147483647, 0)]


def test_an_older_schema_without_the_newer_columns_still_works(tmp_path):
    db = str(tmp_path / 'MyVideos116.db')
    connection = sqlite3.connect(db)
    connection.execute('CREATE TABLE path ( idPath integer primary key, '
                       'strPath text, strContent text, strScraper text, '
                       'strHash text, scanRecursive integer, '
                       'useFolderNames bool, strSettings text, noUpdate bool, '
                       'exclude bool, dateAdded text, idParentPath integer)')
    connection.commit()
    connection.close()
    assert (library_source.ensure_path_content(db, '/x/', 'movies', 's')
            == library_source.ADDED)


def test_a_database_that_is_not_kodis_is_refused(tmp_path):
    db = str(tmp_path / 'MyVideos1.db')
    connection = sqlite3.connect(db)
    connection.execute('CREATE TABLE path (a text)')
    connection.close()
    with pytest.raises(sqlite3.DatabaseError):
        library_source.ensure_path_content(db, '/x/', 'movies', 's')


def test_the_newest_video_database_is_the_one_used(tmp_path):
    folder = str(tmp_path / 'Database')
    _video_db(folder, 116)
    _video_db(folder, 121)
    open(os.path.join(folder, 'MyMusic83.db'), 'w').close()
    assert (library_source.find_video_database(folder)
            == os.path.join(folder, 'MyVideos121.db'))
    assert library_source.find_video_database(str(tmp_path / 'none')) is None


@pytest.mark.parametrize('body, external', [
    (None, False),
    ('<advancedsettings><cache/></advancedsettings>', False),
    ('<advancedsettings><videodatabase><type>sqlite3</type></videodatabase>'
     '</advancedsettings>', False),
    ('<advancedsettings><videodatabase><type>mysql</type><host>nas</host>'
     '</videodatabase></advancedsettings>', True),
    ('<advancedsettings><videodatabase>', True),
])
def test_a_shared_mysql_library_is_left_alone(tmp_path, body, external):
    path = str(tmp_path / 'advancedsettings.xml')
    if body is not None:
        with open(path, 'w') as out:
            out.write(body)
    assert library_source.uses_external_database(path) is external


def test_sources_xml_is_created_when_there_is_none(tmp_path):
    sources = str(tmp_path / 'sources.xml')
    folder = str(tmp_path / 'library' / 'movies')
    assert library_source.ensure_video_source(sources, 'OneDrive movies', folder)
    assert _video_sources(sources) == [('OneDrive movies', folder + os.sep)]


def test_existing_sources_are_kept_and_nothing_is_added_twice(tmp_path):
    sources = str(tmp_path / 'sources.xml')
    original = ('<sources><programs><default pathversion="1"></default>'
                '</programs><video><default pathversion="1"></default>'
                '<source><name>NAS</name><path pathversion="1">smb://nas/films/'
                '</path><allowsharing>true</allowsharing></source></video>'
                '<music><source><name>M</name><path>/m/</path></source></music>'
                '</sources>')
    with open(sources, 'w') as out:
        out.write(original)
    folder = str(tmp_path / 'library' / 'movies') + os.sep

    assert library_source.ensure_video_source(sources, 'NAS', folder)
    assert not library_source.ensure_video_source(sources, 'Other', folder)

    assert _video_sources(sources) == [('NAS', 'smb://nas/films/'),
                                       ('NAS (2)', folder)]
    root = ET.parse(sources).getroot()
    assert root.find('music/source/name').text == 'M'
    assert root.find('programs') is not None
    with open(sources + '.bak') as backup:
        assert backup.read() == original


def test_remembered_sources_are_put_back(tmp_path):
    registry = str(tmp_path / 'library_sources.json')
    sources = str(tmp_path / 'sources.xml')
    folder = str(tmp_path / 'library' / 'tvshows')
    os.makedirs(folder)
    library_source.remember_source(registry, 'OneDrive TV shows', folder)
    library_source.remember_source(registry, 'again', folder + os.sep)
    library_source.remember_source(registry, 'gone', str(tmp_path / 'deleted'))

    assert library_source.restore_sources(registry, sources) == 1
    assert library_source.restore_sources(registry, sources) == 0
    assert _video_sources(sources) == [('OneDrive TV shows', folder + os.sep)]


@pytest.mark.parametrize('folders, has_videos, one_show', [
    ([], True, True),
    (['Season 1', 'Season 2', 'Specials'], False, True),
    (['S01', 'S02'], False, True),
    (['Mùa 1', 'Phần 2'], False, True),
    (['01', '02'], False, True),
    (['Breaking Bad', 'Dark'], False, False),
    (['Season 1', 'Dark'], False, False),
    (['Season 1', 'Dark'], True, True),
])
def test_one_show_or_a_folder_of_shows(folders, has_videos, one_show):
    assert library_source.looks_like_one_show(folders, has_videos) is one_show


# ---------------------------------------------------------------------------
# Through the add-on
# ---------------------------------------------------------------------------

def _kodi_home(tmp_path):
    home = tmp_path / 'kodi'
    userdata = home / 'userdata'
    db = _video_db(str(userdata / 'Database'))
    return str(userdata), db


def _translate(userdata):
    def translate(path):
        for prefix in ('special://masterprofile/', 'special://profile/'):
            if path.startswith(prefix):
                return os.path.join(userdata, path[len(prefix):])
        if path.startswith('special://database/'):
            return os.path.join(userdata, 'Database', '')
        return path
    return translate


def _library_addon(tmp_path, monkeypatch, item, children, choice=None):
    import xbmc
    import xbmcvfs
    from test_quick_access import _library_addon as build

    userdata, db = _kodi_home(tmp_path)
    monkeypatch.setattr(xbmcvfs, 'translatePath', _translate(userdata))
    monkeypatch.setattr(xbmc, 'getCondVisibility',
                        lambda c: c == 'System.HasAddon(metadata.tvshows.themoviedb.org.python)'
                        or c == 'System.HasAddon(metadata.themoviedb.org.python)')
    addon, provider = build(tmp_path, item)
    addon._dialog.choice = choice
    addon._folder_items = lambda *a, **k: children
    os.makedirs(addon._profile_path)
    return addon, userdata, db


def test_movies_are_registered_and_the_user_is_told_where_to_look(
        tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        addon, userdata, db = _library_addon(
            tmp_path, monkeypatch, {'id': 'F1', 'name': 'Phim', 'folder': {}},
            [])
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'movies')

        movies = os.path.join(addon._profile_path, 'library', 'movies') + os.sep
        assert _rows(db) == [(movies, 'movies',
                              'metadata.themoviedb.org.python', 2147483647, 0)]
        assert _video_sources(os.path.join(userdata, 'sources.xml')) == [
            ('string-30101', movies)]
        assert addon._dialog.shown == [('ok', 'registered; see kodi-string-342')]
        assert library_source.read_registry(os.path.join(
            addon._profile_path, library_source.REGISTRY_FILE)) == [
            {'name': 'string-30101', 'path': movies}]


def test_a_folder_of_shows_becomes_a_source_of_its_own(tmp_path, monkeypatch):
    from resources.lib.vendor.clouddrive_common.export import ExportManager
    with kodi_stubs(tmp_path / 'p'):
        addon, userdata, db = _library_addon(
            tmp_path, monkeypatch,
            {'id': 'F1', 'name': 'Phim bộ', 'folder': {}},
            [{'id': 'a', 'name': 'Dark', 'folder': {}},
             {'id': 'b', 'name': 'Breaking Bad', 'folder': {}}])
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'tvshows')

        assert addon._dialog.shown[0] == ('select', 'what is in Phim bộ?', 1)
        collections = os.path.join(addon._profile_path, 'library',
                                   'tvcollections')
        export = ExportManager(addon._profile_path).get_exports()['F1']
        assert export['destination_folder'] == collections
        source = os.path.join(collections, 'Phim bộ') + os.sep
        assert _rows(db) == [(source, 'tvshows',
                              'metadata.tvshows.themoviedb.org.python', 0, 0)]
        assert _video_sources(os.path.join(userdata, 'sources.xml')) == [
            ('string-30102 - Phim bộ', source)]


def test_one_show_goes_under_the_tv_source(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        addon, userdata, db = _library_addon(
            tmp_path, monkeypatch, {'id': 'F1', 'name': 'Dark', 'folder': {}},
            [{'id': 'a', 'name': 'Season 1', 'folder': {}}])
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'tvshows')

        tvshows = os.path.join(addon._profile_path, 'library', 'tvshows') + os.sep
        assert addon._dialog.shown[0] == ('select', 'what is in Dark?', 0)
        assert [r[0] for r in _rows(db)] == [tvshows]


def test_cancelling_the_question_adds_nothing(tmp_path, monkeypatch):
    from resources.lib.vendor.clouddrive_common.export import ExportManager
    with kodi_stubs(tmp_path / 'p'):
        addon, userdata, db = _library_addon(
            tmp_path, monkeypatch, {'id': 'F1', 'name': 'Dark', 'folder': {}},
            [], choice=-1)
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'tvshows')
        assert ExportManager(addon._profile_path).get_exports() == {}
        assert _rows(db) == []


def test_turning_the_setting_off_keeps_the_instructions(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcaddon
        addon, userdata, db = _library_addon(
            tmp_path, monkeypatch, {'id': 'F1', 'name': 'Phim', 'folder': {}},
            [])
        xbmcaddon.Addon.settings['library_auto_source'] = 'false'
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'movies')
        assert _rows(db) == []
        assert not os.path.exists(os.path.join(userdata, 'sources.xml'))
        assert addon._dialog.shown[-1][1].startswith('added; add ')
