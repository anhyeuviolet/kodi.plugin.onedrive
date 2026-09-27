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
"""The export service, kept out of the way of a video being watched.

The vendored service makes its first pass the moment Kodi starts: a Graph
delta call per watched export, .strm and artwork writes for everything that
changed while Kodi was off, and then a scan of the whole video library. That
is exactly when the first video of the session is being opened, so all of it
competed with that video for the network and for Kodi's attention.

This service waits STARTUP_DELAY_SECONDS before its first pass, and never
starts a pass while a video is playing: it looks again every
BUSY_POLL_SECONDS and runs once playback has stopped. Nothing is lost by
waiting -- a watched export works from OneDrive's change token and a
run-immediately flag stays set until a pass consumes it.

It replaces the vendored service from this repository's own `service.py`, so
the vendored file is unchanged.
"""

from resources.lib import library_source
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils
from resources.lib.vendor.clouddrive_common.service.export import ExportService
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils

import datetime
import os

STARTUP_DELAY_SECONDS = 90
BUSY_POLL_SECONDS = 15
PASS_INTERVAL_SECONDS = 60


def video_is_playing():
    import xbmc
    return bool(xbmc.getCondVisibility('Player.HasVideo'))


class PlaybackAwareExportService(ExportService):

    def __init__(self, provider_class, busy=video_is_playing):
        super(PlaybackAwareExportService, self).__init__(provider_class)
        self._busy = busy

    def _wait(self, monitor, seconds):
        """True when Kodi is shutting down."""
        return self.abort or monitor.waitForAbort(seconds)

    def restore_library_sources(self):
        """Put back the library sources Kodi dropped from sources.xml."""
        try:
            restored = library_source.restore_sources(
                os.path.join(self._profile_path, library_source.REGISTRY_FILE),
                KodiUtils.translate_path('special://profile/sources.xml'))
            if restored:
                Logger.notice('library: %d source(s) written back to '
                              'sources.xml; Kodi shows them after a restart'
                              % restored)
        except Exception as e:
            Logger.error(ExceptionUtils.full_stacktrace(e))

    def start(self):
        Logger.notice('Service \'%s\' started.' % self.name)
        self.cleanup_export_map()
        self.restore_library_sources()
        monitor = KodiUtils.get_system_monitor()
        startup = True
        try:
            if self._wait(monitor, STARTUP_DELAY_SECONDS):
                return
            while not self.abort:
                if self._busy():
                    if self._wait(monitor, BUSY_POLL_SECONDS):
                        return
                    continue
                try:
                    now = datetime.datetime.now()
                    export_map = self.get_scheduled_export_map()
                    if export_map:
                        self.process_schedules(export_map, now, startup)
                    self.process_watch()
                except Exception as e:
                    Logger.error(ExceptionUtils.full_stacktrace(e))
                startup = False
                if self._wait(monitor, PASS_INTERVAL_SECONDS):
                    return
        finally:
            del monitor
            Logger.notice('Service stopped.')

    def process_schedules(self, export_map, now, startup=False):
        if startup:
            # The vendored pass runs only the at-startup schedules on its first
            # round, and the run-immediately flags it read on that round were
            # already cleared -- an export added just before Kodi stopped would
            # never run. Run both.
            startup_list = export_map.get(self._startup_type, [])
            immediate = [export for export in export_map.get('run_immediately', [])
                         if export not in startup_list]
            for export in immediate:
                self.run_export(export)
        super(PlaybackAwareExportService, self).process_schedules(
            export_map, now, startup)
