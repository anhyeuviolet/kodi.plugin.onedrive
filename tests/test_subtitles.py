"""Synthetic Graph responses and Kodi recorders for sidecar playback."""

import re
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import unquote, urlsplit

import pytest

from kodistub import kodi_stubs


def entry(name, item_id='subtitle', drive='drive'):
    return {'id': item_id, 'name': name, 'file': {'mimeType': 'text/plain'},
            'parentReference': {'id': 'parent', 'driveId': drive}}


def test_sibling_subtitles_include_other_names_and_all_pages(tmp_path):
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive
        provider = OneDrive()
        provider._driveid = 'drive'
        provider.cancel_operation = lambda: False
        first = {'value': [entry('Movie.mkv'), entry('vi.srt'),
                           {'id': 'folder', 'name': 'Subs.srt', 'folder': {'childCount': 1}}],
                 '@odata.nextLink': 'https://graph.microsoft.com/v1.0/next-page'}
        second = {'value': [entry('Tiếng Việt [CC].ASS', 'ass'),
                            dict(entry('empty.srt', 'empty'), file={})]}
        provider.get = Mock(side_effect=[first, second])
        result = provider.get_subtitles('parent', "O'Neil.mkv")
        assert [s['name'] for s in result] == ['vi.srt', 'Tiếng Việt [CC].ASS', 'empty.srt']
        assert provider.get.call_args_list[0].args == ('/drives/drive/items/parent/children',)
        assert provider.get.call_args_list[1].args == (first['@odata.nextLink'],)


def test_shared_video_looks_in_its_remote_parent(tmp_path):
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive
        provider = OneDrive()
        provider._driveid = 'local'
        remote = entry('Movie.mkv', 'remote-video', 'remote-drive')
        remote['parentReference']['id'] = 'remote-parent'
        provider.get = Mock(return_value={'id': 'shortcut', 'remoteItem': remote})
        provider.get_subtitles = Mock(return_value=[{'id': 'sidecar'}])
        result = provider.get_item('local', 'shortcut', find_subtitles=True)
        provider.get_subtitles.assert_called_once_with('remote-parent', 'Movie.mkv', 'remote-drive', False)
        assert result['subtitles'] == [{'id': 'sidecar'}]


def test_missing_parent_and_cancelled_listing_return_no_subtitles(tmp_path):
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.provider.onedrive import OneDrive
        provider = OneDrive()
        provider._driveid = 'drive'
        provider.get = Mock(return_value={'value': [entry('vi.srt')]})
        assert provider.get_subtitles(None, 'Movie.mkv') == []
        provider.get.assert_not_called()
        provider.cancel_operation = lambda: True
        assert provider.get_subtitles('parent', 'Movie.mkv') == []


@pytest.mark.parametrize('subtitles', [[], [{'id': 'sub', 'name': 'vi.srt'}]])
@pytest.mark.parametrize('old_cache', [None, {'id': 'video', 'name': 'Movie.mkv'}])
def test_source_cache_returns_a_list_on_repeated_playback(tmp_path, subtitles, old_cache):
    with kodi_stubs(tmp_path / 'profile'):
        from resources.lib.vendor.clouddrive_common.service.source import Source
        cache = {'drive/Movie.mkv-subtitles': old_cache}
        provider = SimpleNamespace(configure=Mock(), get_subtitles=Mock(return_value=subtitles))
        source = SimpleNamespace(
            get_item=Mock(return_value={'id': 'video', 'name': 'Movie.mkv', 'parent': 'parent'}),
            _items_cache=SimpleNamespace(get=cache.get, set=cache.__setitem__),
            _get_provider=lambda: provider, _account_manager=None, is_path_possible=Mock())
        assert Source.get_subtitles(source, 'drive', '/Movie.mkv') == subtitles
        assert Source.get_subtitles(source, 'drive', '/Movie.mkv') == subtitles
        provider.get_subtitles.assert_called_once()


def player_module(monkeypatch):
    import xbmc
    monkeypatch.setattr(xbmc, 'Player', object, raising=False)
    from resources.lib.vendor.clouddrive_common.service import player
    monkeypatch.setattr(player.KodiUtils, 'get_home_property', lambda *args: '')
    return player


def test_http_lookup_waits_for_av_started(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'profile'):
        module = player_module(monkeypatch)
        monkeypatch.setattr(module.KodiUtils, 'get_addon_setting', lambda *args: 'true')
        thread = Mock()
        monkeypatch.setattr(module.threading, 'Thread', thread)
        player = module.KodiPlayer()
        player.isPlaying = lambda: True
        player.getPlayingFile = lambda: 'http://localhost:8000/source/Movie.mkv'
        player.set_source_url_matcher(re.compile('http://localhost:8000/source/'))
        player.onPlayBackStarted()
        thread.assert_not_called()
        player.onAVStarted()
        assert thread.call_args.kwargs['args'] == (player.getPlayingFile(), 1)
        thread.return_value.start.assert_called_once()


@pytest.mark.parametrize('change', ['none', 'stop', 'next', 'replay', 'bad-cache'])
def test_http_subtitles_are_only_applied_to_current_playback(tmp_path, monkeypatch, change):
    with kodi_stubs(tmp_path / 'profile'):
        module = player_module(monkeypatch)
        from resources.lib.vendor.clouddrive_common.remote.request import Request
        from resources.lib.vendor.clouddrive_common.service.download import DownloadServiceUtil
        player = module.KodiPlayer()
        original = 'http://localhost:8000/source/Movie.mkv'
        player.isPlaying = lambda: True
        player.getPlayingFile = lambda: original
        player.setSubtitles = Mock()
        def response(*args):
            if change == 'stop':
                player.isPlaying = lambda: False
            elif change == 'next':
                player.getPlayingFile = lambda: original + '.next'
            elif change == 'replay':
                player._playback_generation += 1
            subs = [{'id': 'sub', 'name': 'Tiếng Việt.srt'}]
            return {'driveid': 'drive', 'subtitles': {} if change == 'bad-cache' else subs}
        monkeypatch.setattr(Request, 'request_json', response)
        monkeypatch.setattr(DownloadServiceUtil, 'build_download_url', lambda *args: 'http://localhost/' + args[3])
        player.get_subtitles(original, 0)
        if change == 'none':
            player.setSubtitles.assert_called_once()
            assert unquote(player.setSubtitles.call_args.args[0]).endswith('Tiếng Việt.srt')
        else:
            player.setSubtitles.assert_not_called()


def test_plugin_play_passes_once_encoded_sidecars_to_kodi(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'profile'):
        module = player_module(monkeypatch)
        monkeypatch.setattr(module.KodiPlayer, 'cleanup', lambda: None)
        from resources.lib.vendor.clouddrive_common.ui.addon import CloudDriveAddon
        from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
        import xbmcgui
        import xbmcplugin
        list_item = Mock()
        monkeypatch.setattr(xbmcgui, 'ListItem', Mock(return_value=list_item))
        resolved = Mock()
        monkeypatch.setattr(xbmcplugin, 'setResolvedUrl', resolved, raising=False)
        monkeypatch.setattr(KodiUtils, 'get_current_library_info', lambda: None)
        monkeypatch.setattr(KodiUtils, 'find_exported_video_in_library', lambda *args: None)
        monkeypatch.setattr(KodiUtils, 'get_service_port', lambda *args: 8000)
        video = {'id': 'video', 'name': 'Movie.mkv', 'subtitles': [
            {'id': 'sub', 'name': 'Tiếng Việt [100%].srt', 'drive_id': 'remote'}]}
        provider = SimpleNamespace(configure=Mock(), get_item=Mock(return_value=video))
        addon = object.__new__(CloudDriveAddon)
        addon._addon = SimpleNamespace(getSetting=lambda *args: 'true')
        addon._content_type = 'video'
        addon._account_manager = None
        for attribute in ('_common_addon', '_dialog', '_progress_dialog',
                          '_progress_dialog_bg', '_system_monitor'):
            setattr(addon, attribute, None)
        addon._addon_handle = 1
        addon.get_provider = lambda: provider
        addon.cancel_operation = lambda: False
        addon.play('drive', 'drive', 'video')
        urls = list_item.setSubtitles.call_args.args[0]
        assert len(urls) == 1
        assert unquote(urlsplit(urls[0]).path) == '/download/drive/remote/sub/Tiếng Việt [100%].srt'
        resolved.assert_called_once_with(1, True, list_item)
