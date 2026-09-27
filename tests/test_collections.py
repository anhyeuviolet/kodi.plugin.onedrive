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
"""A folder's videos as Favourites, or as a playlist, in one step."""

import json
import os
import urllib.parse

import pytest

from kodistub import kodi_stubs
from resources.lib import quickaccess


def _video(item_id, name, drive_id=None):
    item = {'id': item_id, 'name': name, 'name_extension': 'mkv', 'size': 1,
            'video': {}, 'thumbnail': 'https://thumb/' + item_id}
    if drive_id:
        item['drive_id'] = drive_id
    return item


def _folder(item_id, name):
    return {'id': item_id, 'name': name, 'folder': {}}


# Dark/                      <- chosen
#   Season 10/ E1
#   Season 2/  Episode 10, Episode 2
#   Trailer.mkv, notes.txt
TREE = {
    'F1': [_folder('S10', 'Season 10'), _folder('S2', 'Season 2'),
           _video('T', 'Trailer.mkv'),
           {'id': 'N', 'name': 'notes.txt', 'name_extension': 'txt'}],
    'S2': [_video('E10', 'Episode 10.mkv'), _video('E2', 'Episode 2.mkv')],
    'S10': [_video('X1', 'E1.mkv', drive_id='other-drive')],
}


def _is_video(item):
    return 'video' in item


def _children(folder):
    return TREE.get(folder['id'], [])


def test_videos_come_in_watching_order():
    videos, complete = quickaccess.collect_videos(_children, {'id': 'F1'},
                                                  _is_video)
    assert complete
    assert [(folders, v['name']) for folders, v in videos] == [
        ([], 'Trailer.mkv'),
        (['Season 2'], 'Episode 2.mkv'),
        (['Season 2'], 'Episode 10.mkv'),
        (['Season 10'], 'E1.mkv')]


def test_a_walk_cut_short_says_so():
    _, complete = quickaccess.collect_videos(_children, {'id': 'F1'},
                                             _is_video, max_depth=0)
    assert not complete
    videos, complete = quickaccess.collect_videos(_children, {'id': 'F1'},
                                                  _is_video, max_listings=2)
    assert not complete and len(videos) == 2
    videos, complete = quickaccess.collect_videos(_children, {'id': 'F1'},
                                                  _is_video, limit=1)
    assert not complete and len(videos) == 1


@pytest.mark.parametrize('folders, name, label', [
    ([], 'Film.2020.mkv', 'Film.2020'),
    (['Season 1'], 'Episode 01.mp4', 'Season 1 - Episode 01'),
    ([], '.hidden', '.hidden'),
    ([], 'noext', 'noext'),
])
def test_labels(folders, name, label):
    assert quickaccess.video_label(folders, name) == label


def test_a_favourite_is_never_added_twice():
    candidates = [{'path': 'a'}, {'path': 'b'}, {'path': 'a'}, {'path': 'c'}]
    assert quickaccess.favourites_to_add({'b'}, candidates) == [
        {'path': 'a'}, {'path': 'c'}]


@pytest.mark.parametrize('name, filename', [
    ('Phim bộ', 'OneDrive - Phim bộ.m3u'),
    ('a/b\\c:d*e?"f<g>h|', 'OneDrive - a b c d e f g h.m3u'),
    ('...', 'OneDrive - OneDrive.m3u'),
])
def test_playlist_names_are_safe_file_names(name, filename):
    assert quickaccess.playlist_filename(name) == filename


def test_m3u_text():
    assert quickaccess.m3u_playlist([('A\nB', 'plugin://x/?a=1')]) == (
        '#EXTM3U\n#EXTINF:-1,A B\nplugin://x/?a=1\n')


# ---------------------------------------------------------------------------
# Through the add-on
# ---------------------------------------------------------------------------

class _JsonRpc(object):
    def __init__(self, favourites=()):
        self.favourites = [{'title': 't', 'type': 'media', 'path': p}
                           for p in favourites]
        self.added = []

    def __call__(self, command):
        request = json.loads(command)
        method, params = request['method'], request.get('params', {})
        if method == 'Favourites.GetFavourites':
            result = {'favourites': self.favourites or None,
                      'limits': {'total': len(self.favourites)}}
        elif method == 'Favourites.AddFavourite':
            self.added.append(params)
            result = 'OK'
        else:
            raise AssertionError(method)
        return json.dumps({'id': 1, 'jsonrpc': '2.0', 'result': result})


def _addon(tmp_path, monkeypatch, rpc, choose=None):
    import xbmc
    import xbmcvfs
    from test_quick_access import _library_addon

    monkeypatch.setattr(xbmc, 'executeJSONRPC', rpc, raising=False)
    playlists = str(tmp_path / 'userdata' / 'playlists' / 'video')
    monkeypatch.setattr(
        xbmcvfs, 'translatePath',
        lambda p: playlists + os.sep if p == 'special://profile/playlists/video/'
        else p)
    addon, provider = _library_addon(
        tmp_path, {'id': 'F1', 'name': 'Dark', 'folder': {}})
    addon._folder_items = (lambda driveid, item_driveid=None, item_id=None,
                           path=None, progress=True: TREE.get(item_id, []))
    dialog = addon._dialog

    def multiselect(heading, options, preselect=None, **kwargs):
        dialog.shown.append(('multiselect', options, preselect))
        return choose(options) if choose else preselect
    dialog.multiselect = multiselect
    notes = []
    from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
    monkeypatch.setattr(KodiUtils, 'show_notification',
                        lambda msg, time=5000: notes.append(msg))
    os.makedirs(addon._profile_path)
    return addon, notes, playlists


def _query(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


def test_every_video_is_offered_ticked_and_added(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        rpc = _JsonRpc()
        addon, notes, _ = _addon(tmp_path, monkeypatch, rpc)
        import xbmcaddon
        xbmcaddon.Addon.strings[30106] = 'added %s, skipped %s'

        addon._add_to_favourites('drive-1', 'drive-1', 'F1')

        offered = addon._dialog.shown[0]
        assert offered == ('multiselect',
                           ['Trailer', 'Season 2 - Episode 2',
                            'Season 2 - Episode 10', 'Season 10 - E1'],
                           [0, 1, 2, 3])
        assert [a['title'] for a in rpc.added] == offered[1]
        assert all(a['type'] == 'media' for a in rpc.added)
        last = _query(rpc.added[-1]['path'])
        assert last == {'content_type': 'video', 'item_driveid': 'other-drive',
                        'item_id': 'X1', 'driveid': 'drive-1', 'action': 'play'}
        assert rpc.added[0]['thumbnail'] == 'https://thumb/T'
        assert notes == ['added 4, skipped 0']


def test_favourites_already_there_are_skipped(tmp_path, monkeypatch):
    """AddFavourite takes away a favourite it is given a second time."""
    with kodi_stubs(tmp_path / 'p'):
        import xbmcaddon
        probe_rpc = _JsonRpc()
        addon, notes, _ = _addon(tmp_path, monkeypatch, probe_rpc)
        existing = addon._play_url('drive-1', 'drive-1', 'T')
        rpc = _JsonRpc([existing])
        import xbmc
        monkeypatch.setattr(xbmc, 'executeJSONRPC', rpc, raising=False)
        xbmcaddon.Addon.strings[30106] = 'added %s, skipped %s'

        addon._add_to_favourites('drive-1', 'drive-1', 'F1')

        assert existing not in [a['path'] for a in rpc.added]
        assert len(rpc.added) == 3
        assert notes == ['added 3, skipped 1']


def test_the_path_matches_the_row_kodi_would_add_by_hand(tmp_path, monkeypatch):
    """A favourite made from the folder listing is recognised as the same."""
    with kodi_stubs(tmp_path / 'p') as recorder:
        import xbmcgui
        for name in ('addStreamInfo', 'setInfo', 'setArt',
                     'addContextMenuItems', 'setProperty'):
            if not hasattr(xbmcgui.ListItem, name):
                monkeypatch.setattr(xbmcgui.ListItem, name,
                                    lambda self, *a, **k: None, raising=False)
        addon, _, _ = _addon(tmp_path, monkeypatch, _JsonRpc())
        addon._process_items([_video('T', 'Trailer.mkv')], 'drive-1')
        row_url = recorder.directory_items[0][0]
        assert row_url == addon._play_url('drive-1', 'drive-1', 'T')


def test_unticking_everything_adds_nothing(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        rpc = _JsonRpc()
        addon, notes, _ = _addon(tmp_path, monkeypatch, rpc,
                                 choose=lambda options: [])
        addon._add_to_favourites('drive-1', 'drive-1', 'F1')
        assert rpc.added == [] and notes == []


def test_a_folder_without_videos_says_so(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        rpc = _JsonRpc()
        addon, _, _ = _addon(tmp_path, monkeypatch, rpc)
        addon._folder_items = lambda *a, **k: []
        addon._add_to_favourites('drive-1', 'drive-1', 'F1')
        assert addon._dialog.shown == [('ok', 'string-30107')]


def test_a_playlist_is_written_under_videos_playlists(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcaddon
        xbmcaddon.Addon.strings[30108] = 'saved %s with %s'
        addon, notes, playlists = _addon(tmp_path, monkeypatch, _JsonRpc())

        addon._create_playlist('drive-1', 'drive-1', 'F1')

        target = os.path.join(playlists, 'OneDrive - Dark.m3u')
        with open(target, encoding='utf-8') as written:
            lines = written.read().splitlines()
        assert lines[0] == '#EXTM3U'
        assert lines[1::2] == ['#EXTINF:-1,Trailer',
                                   '#EXTINF:-1,Season 2 - Episode 2',
                                   '#EXTINF:-1,Season 2 - Episode 10',
                                   '#EXTINF:-1,Season 10 - E1']
        assert _query(lines[2])['item_id'] == 'T'
        assert all(line.startswith('plugin://plugin.onedrive.kn/')
                   for line in lines[2::2])
        assert notes == ['saved OneDrive - Dark.m3u with 4']


def test_an_existing_playlist_is_replaced_only_when_the_user_agrees(
        tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcaddon
        xbmcaddon.Addon.strings[30109] = 'replace %s?'
        addon, notes, playlists = _addon(tmp_path, monkeypatch, _JsonRpc())
        os.makedirs(playlists)
        target = os.path.join(playlists, 'OneDrive - Dark.m3u')
        with open(target, 'w') as out:
            out.write('mine')
        addon._create_playlist('drive-1', 'drive-1', 'F1')   # yesno -> False
        with open(target) as kept:
            assert kept.read() == 'mine'
        assert notes == []
