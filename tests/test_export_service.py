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
"""The export service keeps out of the way of the video being watched."""

from kodistub import kodi_stubs


class _Monitor(object):
    """Aborts after `rounds` waits, recording how long each one was."""

    def __init__(self, rounds):
        self.waits = []
        self._rounds = rounds

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        return len(self.waits) >= self._rounds


def _service(tmp_path, monkeypatch, busy, rounds):
    from resources.lib import export_service
    from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils

    monitor = _Monitor(rounds)
    monkeypatch.setattr(KodiUtils, 'get_system_monitor', lambda: monitor)
    service = object.__new__(export_service.PlaybackAwareExportService)
    # What the vendored __del__ deletes.
    for name in ('_system_monitor', 'export_manager', '_account_manager',
                 '_common_addon', '_export_progress_dialog_bg'):
        setattr(service, name, None)
    service.abort = False
    service._busy = busy
    service._profile_path = str(tmp_path)
    service._startup_type = '1'
    service.passes = []
    service.cleanup_export_map = lambda: None
    service.get_scheduled_export_map = lambda: {}
    service.process_watch = lambda: service.passes.append('watch')
    return export_service, service, monitor


def test_the_first_pass_waits_for_kodi_to_settle(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        module, service, monitor = _service(tmp_path, monkeypatch,
                                            lambda: False, rounds=2)
        service.start()
        assert monitor.waits == [module.STARTUP_DELAY_SECONDS,
                                 module.PASS_INTERVAL_SECONDS]
        assert service.passes == ['watch']


def test_nothing_runs_while_a_video_plays(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        playing = iter([True, True, False])
        module, service, monitor = _service(
            tmp_path, monkeypatch, lambda: next(playing), rounds=4)
        service.start()
        assert monitor.waits == [module.STARTUP_DELAY_SECONDS,
                                 module.BUSY_POLL_SECONDS,
                                 module.BUSY_POLL_SECONDS,
                                 module.PASS_INTERVAL_SECONDS]
        assert service.passes == ['watch'], 'one pass, once playback stopped'


def test_an_export_added_just_before_a_restart_still_runs(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        module, service, monitor = _service(tmp_path, monkeypatch,
                                            lambda: False, rounds=2)
        ran = []
        service.run_export = lambda export: ran.append(export['id'])
        waiting = {'id': 'new'}
        at_startup = {'id': 'startup'}
        service.get_scheduled_export_map = lambda: {
            'run_immediately': [waiting], '1': [at_startup]}
        service.start()
        assert sorted(ran) == ['new', 'startup']


def test_remembered_library_sources_are_restored_at_start(tmp_path, monkeypatch):
    from resources.lib import library_source
    with kodi_stubs(tmp_path / 'p'):
        import xbmcvfs
        sources = str(tmp_path / 'sources.xml')
        monkeypatch.setattr(xbmcvfs, 'translatePath',
                            lambda path: sources if path.endswith('sources.xml')
                            else path)
        folder = tmp_path / 'library' / 'movies'
        folder.mkdir(parents=True)
        library_source.remember_source(
            str(tmp_path / library_source.REGISTRY_FILE), 'OneDrive movies',
            str(folder))
        module, service, monitor = _service(tmp_path, monkeypatch,
                                            lambda: False, rounds=1)
        service.start()
        with open(sources) as written:
            assert str(folder) in written.read()
