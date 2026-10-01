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
"""OneDrive as a Kodi source (http://127.0.0.1:<port>/source/), fixed twice.

The vendored source service lets Kodi browse the drive as an ordinary web
folder -- added under Videos > Files, given a content type and scanned into
the library with no .strm files at all. Two things kept it from working:

  * A file was answered with a redirect to OneDrive's pre-authenticated
    download URL. That is exactly the link the add-on's own playback stopped
    using (resources/lib/streaming.py): it expires after about an hour, Kodi
    keeps using it for every later request, and the video stops partway.
    The redirect now points at the loopback download service instead, which
    relays the file and renews the link -- so a video played from the source
    behaves as one played from the add-on.

  * The setting "Allow using OneDrive as a source" was read once, when Kodi
    started; switching it on did nothing until a restart, which nothing said.
    The service now looks at the setting every few seconds and starts
    listening as soon as it is on.

The listener stays off until the user turns it on (VENDORED.md, "Recorded
behaviour deviations"): it serves an index of the drive to any program on the
box, without asking for anything.
"""

import urllib.parse

from resources.lib.vendor.clouddrive_common.service.download import (
    DownloadServiceUtil)
from resources.lib.vendor.clouddrive_common.service.source import (
    Source, SourceService)
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
from resources.lib.vendor.clouddrive_common.utils import Utils

SETTING_POLL_SECONDS = 5


def relay_url(driveid, item):
    """The loopback download address that relays `item`."""
    item_driveid = Utils.default(Utils.get_safe_value(item, 'drive_id'), driveid)
    return DownloadServiceUtil.build_download_url(
        driveid, item_driveid, item['id'],
        urllib.parse.quote(Utils.str(item['name'])))


class RelayingSource(Source):

    def get_download_url(self, driveid, path):
        item = self.get_item(driveid, path)
        if 'folder' in item:
            return self.path + '/'
        return relay_url(driveid, item)


class RelayingSourceService(SourceService):

    def __init__(self, provider_class):
        super(RelayingSourceService, self).__init__(provider_class,
                                                    RelayingSource)
        self.abort = False

    @staticmethod
    def enabled():
        return KodiUtils.get_addon_setting('allow_directory_listing') == 'true'

    def start(self):
        monitor = KodiUtils.get_system_monitor()
        try:
            while not self.abort and not self.enabled():
                if monitor.waitForAbort(SETTING_POLL_SECONDS):
                    return
        finally:
            del monitor
        if self.abort:
            return
        Logger.notice('source: OneDrive is served as a Kodi source')
        super(RelayingSourceService, self).start()

    def stop(self):
        self.abort = True
        super(RelayingSourceService, self).stop()
