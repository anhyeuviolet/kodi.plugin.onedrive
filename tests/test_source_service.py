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
"""OneDrive as a Kodi source plays through the relay, and turns on at once."""

from kodistub import kodi_stubs


def test_a_file_in_the_source_goes_through_the_relay(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import importlib
        import xbmcaddon
        source_service = importlib.import_module('resources.lib.source_service')
        xbmcaddon.Addon.settings['download.service.port'] = '40123'
        source = object.__new__(source_service.RelayingSource)
        source.path = '/source/OneDrive%20KN/Kenny/Phim/Film%201.mkv'
        items = {
            '/Phim/Film 1.mkv': {'id': 'ITEM', 'name': 'Film 1.mkv',
                                 'drive_id': 'shared-drive',
                                 'download_info': {'url': 'https://cdn/signed'}},
            '/Phim': {'id': 'DIR', 'name': 'Phim', 'folder': {}},
        }
        source.get_item = lambda driveid, path: items[path]

        url = source.get_download_url('drive-1', '/Phim/Film 1.mkv')
        assert url == ('http://127.0.0.1:40123/download/drive-1/shared-drive/'
                       'ITEM/Film%201.mkv')
        assert 'cdn' not in url, 'the expiring link must never reach Kodi'
        assert (source.get_download_url('drive-1', '/Phim')
                == source.path + '/')


class _Monitor(object):
    def __init__(self, on_wait):
        self.waits = 0
        self._on_wait = on_wait

    def waitForAbort(self, seconds):
        self.waits += 1
        return self._on_wait(self.waits)


def _service(monkeypatch, on_wait):
    import importlib
    # Through sys.modules, not the package attribute: another test may have
    # left `resources.lib.source_service` bound to a copy imported earlier.
    source_service = importlib.import_module('resources.lib.source_service')
    monitor = _Monitor(on_wait)
    monkeypatch.setattr(source_service.KodiUtils, 'get_system_monitor',
                        lambda: monitor)
    served = []
    monkeypatch.setattr(source_service.SourceService, 'start',
                        lambda self: served.append(1))
    service = object.__new__(source_service.RelayingSourceService)
    service.abort = False
    service._server = None
    return service, monitor, served


def test_turning_the_setting_on_starts_the_source_without_a_restart(
        tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcaddon

        def turn_on_later(waits):
            if waits == 3:
                xbmcaddon.Addon.settings['allow_directory_listing'] = 'true'
            return False
        service, monitor, served = _service(monkeypatch, turn_on_later)
        service.start()
        assert monitor.waits == 3 and served == [1]


def test_kodi_stopping_while_it_is_off_starts_nothing(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        service, monitor, served = _service(monkeypatch, lambda waits: True)
        service.start()
        assert served == []


# ---------------------------------------------------------------------------
# Folder names with a space or a letter outside ASCII
# ---------------------------------------------------------------------------

class _Cache(object):
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def setmany(self, pairs):
        for key, value in pairs:
            self.values[key] = value


class _Provider(object):
    def __init__(self):
        self.paths = []

    def configure(self, account_manager, driveid):
        pass

    def get_folder_items(self, path=None, **kwargs):
        self.paths.append(path)
        return [{'id': 'E1', 'name': 'Tập 1.mkv'}]

    def get_item(self, path=None, **kwargs):
        self.paths.append(path)
        return {'id': 'E1', 'name': 'Tập 1.mkv'}


def test_kodis_encoded_address_reaches_graph_decoded(tmp_path):
    """Before, 'Phim%20b%E1%BB%99' went to Graph as a name and was not found."""
    with kodi_stubs(tmp_path / 'p'):
        import importlib
        source_service = importlib.import_module('resources.lib.source_service')
        provider = _Provider()

        class _Server(object):
            @staticmethod
            def data(source_mode=False):
                return provider
        source = object.__new__(source_service.RelayingSource)
        source.server = _Server()
        source._account_manager = None
        source._items_cache = _Cache()
        source._children_cache = _Cache()

        items = source.get_folder_items('drive-1', '/Phim%20b%E1%BB%99/')
        source.get_item('drive-1', '/M%E1%BB%9Bi/T%E1%BA%ADp%201.mkv')

        assert provider.paths == ['/Phim bộ', '/Mới/Tập 1.mkv']
        assert items[0]['id'] == 'E1'
        # The service's own caches keep the encoded form Kodi asks with.
        assert (source._children_cache.get('drive-1/Phim%20b%E1%BB%99:children')
                == ['T%E1%BA%ADp%201.mkv'])
