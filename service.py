#-------------------------------------------------------------------------------
# Copyright (C) 2017 Carlos Guzman (cguZZman) carlosguzmang@protonmail.com
# 
# This file is part of OneDrive for Kodi
# 
# OneDrive for Kodi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Cloud Drive Common Module for Kodi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------

from resources.lib.startup_refresh import StartupRefreshService
from resources.lib.vendor.clouddrive_common.service.download import DownloadService
from resources.lib.vendor.clouddrive_common.service.source import SourceService
from resources.lib.vendor.clouddrive_common.service.utils import ServiceUtil
from resources.lib.provider.onedrive import OneDrive
from resources.lib.vendor.clouddrive_common.service.export import ExportService
from resources.lib.vendor.clouddrive_common.service.player import PlayerService


# The four listeners, and one keepalive.
#
# The keepalive is last for the same reason it is here at all. `ServiceUtil.run`
# starts each of these once, in its own daemon thread, and then waits for the
# shutdown; it has no periodic set, so a service whose `start` returns has run
# exactly once at Kodi start -- which is what a keepalive wants and what a
# refresh on every poll would ruin, since every write is a chance to leave a
# temporary file behind on a device that is power-cut rather than shut down.
# Last in the list means the four servers have claimed their ports before the
# token exchange begins, and running inside the runner rather than before it
# means the exchange delays none of them.
#
# The four above are untouched. One of them is scheduled for deletion in a later
# phase on security grounds and this is not that phase: doing it here would put
# two unrelated changes in one commit and make the bisect that finds either of
# them ambiguous.
if __name__ == '__main__':
    ServiceUtil.run([DownloadService(OneDrive), SourceService(OneDrive),
                     ExportService(OneDrive), PlayerService(OneDrive),
                     StartupRefreshService(OneDrive)])