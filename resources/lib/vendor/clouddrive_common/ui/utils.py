#-------------------------------------------------------------------------------
# Copyright (C) 2017 Carlos Guzman (cguZZman) carlosguzmang@protonmail.com
# 
# This file is part of Cloud Drive Common Module for Kodi
# 
# Cloud Drive Common Module for Kodi is free software: you can redistribute it and/or modify
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


from threading import Lock
import threading
import time
import urllib.parse

class KodiUtils:
    HOME_WINDOW = 10000
    LOGDEBUG = 0
    LOGNOTICE = 1
    LOGWARNING = 2
    LOGERROR = 3
    lock = Lock()
    # None means "the calling add-on": get_addon() then constructs
    # xbmcaddon.Addon() with no argument, so the common add-on and this
    # add-on are the same object rather than two that happen to agree.
    common_addon_id = None
    
    @staticmethod
    def get_addon(addonid=None):
        import xbmcaddon
        if addonid:
            return xbmcaddon.Addon(addonid)
        else:
            return xbmcaddon.Addon()
    @staticmethod
    def get_common_addon():
        return KodiUtils.get_addon(KodiUtils.common_addon_id)
    
    @staticmethod
    def get_common_addon_path():
        from resources.lib.vendor.clouddrive_common.utils import Utils
        return Utils.unicode(KodiUtils.get_addon_info("path", KodiUtils.common_addon_id))
    
    # Kodi reserves 30000-33000 for an add-on's own strings and keeps everything
    # below 30000 for itself. Anything at or above the boundary therefore
    # belongs to an add-on's catalogue and anything below it to Kodi's.
    ADDON_STRING_FLOOR = 30000

    @staticmethod
    def localize(string_id, addonid=None, addon=None):
        """A string, from whichever catalogue owns its id.

        The boundary was 32000 until this add-on was renumbered into the 30000
        block, and it was right when the only add-on ids in the tree were the
        vendored module's 32000-32088. It stopped being right the moment this
        add-on's own strings moved down, and it failed silently: 30042 went to
        Kodi's catalogue and came back as Kodi's 30042, so a caller got the
        wrong sentence rather than an error.

        No shipped caller passes an id in this add-on's block today -- the four
        core ids that reach here, 1210, 12021 and 21479, are all below the
        boundary either way -- so this is a latent fault being closed rather
        than a visible one being fixed. test_localize_owns_this_addons_block in
        tests/test_vendor_gates.py holds the boundary against the same
        partition set the catalogue is asserted against, so the two cannot move
        apart again.
        """
        if string_id < KodiUtils.ADDON_STRING_FLOOR:
            import xbmc
            return xbmc.getLocalizedString(string_id)
        if not addon:
            addon = KodiUtils.get_addon(addonid)
        return addon.getLocalizedString(string_id)
    
    @staticmethod
    def create_list_item(id, label):
        import xbmcgui
        from resources.lib.vendor.clouddrive_common.utils import Utils
        list_item = xbmcgui.ListItem(label)
        list_item.setProperty('id', Utils.str(id))
        return list_item
    
    @staticmethod
    def get_language_code():
        import xbmc
        return xbmc.getLanguage(format=xbmc.ISO_639_1, region=True)
         
    @staticmethod
    def get_system_monitor():
        import xbmc
        return xbmc.Monitor()
    
    @staticmethod
    def get_window(window_id):
        import xbmcgui
        return xbmcgui.Window(window_id)
    
    @staticmethod
    def get_current_window_id():
        import xbmcgui
        return xbmcgui.getCurrentWindowId()
    
    @staticmethod
    def get_supported_media(media_type):
        import xbmc
        return xbmc.getSupportedMedia(media_type).replace(".","").split("|")
    
    @staticmethod
    def execute_json_rpc(method, params=None, request_id=1):
        import xbmc
        import json
        cmd = {'jsonrpc': '2.0', 'method': method, 'id': request_id}
        if params:
            cmd['params'] = params
        cmd = json.dumps(cmd)
        return json.loads(xbmc.executeJSONRPC(cmd)) 
    
    @staticmethod
    def get_cond_visibility(cmd):
        import xbmc
        xbmc.getCondVisibility(cmd)
        
    @staticmethod
    def update_library(database, wait=False):
        KodiUtils.executebuiltin('UpdateLibrary(%s)' % database, wait)
        
    @staticmethod
    def executebuiltin(cmd, wait=False):
        import xbmc
        xbmc.executebuiltin(cmd, wait)
        
    @staticmethod
    def run_script(script, params=None, wait=False):
        import xbmc
        if params:
            params = urllib.parse.urlencode(params)
        cmd = 'RunScript(%s,0,?%s)' % (script, params)
        xbmc.executebuiltin(cmd, wait)
        
    @staticmethod
    def run_plugin(addonid, params=None, wait=False):
        import xbmc
        url = 'plugin://%s/' % addonid
        if params:
            url += '?%s' % urllib.parse.urlencode(params)
        cmd = 'RunPlugin(%s)' % url
        xbmc.executebuiltin(cmd, wait)
        
    @staticmethod
    def activate_window(addon_url, window_id=None, params=None, wait=False):
        import xbmc
        if not window_id:
            window_id = KodiUtils.get_current_window_id()
        if params:
            addon_url += '?%s' % urllib.parse.urlencode(params)
        cmd = 'ActivateWindow(%d,%s)' % (window_id, addon_url)
        xbmc.executebuiltin(cmd, wait)
        
    @staticmethod
    def replace_window(addon_url, window_id=None, params=None, wait=False):
        import xbmc
        if not window_id:
            window_id = KodiUtils.get_current_window_id()
        if params:
            addon_url += '?%s' % urllib.parse.urlencode(params)
        cmd = 'ReplaceWindow(%d,%s)' % (window_id, addon_url)
        xbmc.executebuiltin(cmd, wait)
    
    @staticmethod
    def is_addon_enabled(addonid):
        response = KodiUtils.execute_json_rpc('Addons.GetAddonDetails', {'addonid': addonid})
        return response["result"]["addon"]["enabled"]

    @staticmethod
    def get_addon_setting(setting_id, addonid=None):
        addon = KodiUtils.get_addon(addonid)
        setting = addon.getSetting(setting_id)
        del addon
        return setting
    
    @staticmethod
    def set_addon_setting(setting_id, value, addonid=None):
        from resources.lib.vendor.clouddrive_common.utils import Utils
        addon = KodiUtils.get_addon(addonid)
        setting = addon.setSetting(setting_id, Utils.str(value))
        del addon
        return setting
    
    @staticmethod
    def get_addon_info(info_id, addonid=None):
        addon = KodiUtils.get_addon(addonid)
        info = addon.getAddonInfo(info_id)
        del addon
        return info
    
    
    @staticmethod
    def show_notification(msg, time=5000):
        import xbmcgui
        from resources.lib.vendor.clouddrive_common.utils import Utils
        xbmcgui.Dialog().notification(KodiUtils.get_addon_info('name'), msg, Utils.unicode(KodiUtils.get_addon_info('path') + '/icon.png'), time)
    
    @staticmethod
    def get_service_port(service, addonid=None):
        with KodiUtils.lock:
            port = KodiUtils.get_addon_setting('%s.service.port' % service, addonid)
        return port

    @staticmethod
    def set_service_port(service, port, addonid=None):
        from resources.lib.vendor.clouddrive_common.utils import Utils
        with KodiUtils.lock:
            KodiUtils.set_addon_setting('%s.service.port' % service, Utils.str(port), addonid)
    
    # An accessor stood here that read the address of a hosted third party out
    # of a setting. It was the only address source the error reporter and the
    # replaced sign-in flow ever had; both are gone, so it is too. Its
    # neighbours above and below -- the service-port helpers, the cache-expiry
    # accessor, the notification helper -- are unrelated and stay (AUTH-23).
    # VENDORED.md carries the name and the history; naming it here would put it
    # back into shipped source, which is the one thing the sweep forbids.

    @staticmethod
    def get_cache_expiration_time(addonid=None):
        from resources.lib.vendor.clouddrive_common.utils import Utils
        return int(Utils.default(KodiUtils.get_addon_setting('cache-expiration-time', addonid), '5'))
    
    @staticmethod
    def log(msg, level):
        import xbmc
        from resources.lib.vendor.clouddrive_common.utils import Utils
        if level == 0:
            level = xbmc.LOGDEBUG
        elif level == 1:
            level = xbmc.LOGINFO
        elif level == 2:
            level = xbmc.LOGWARNING
        elif level == 3:
            level = xbmc.LOGERROR
        xbmc.log(u'[%s][%s-%s]: %s' % (KodiUtils.get_addon_info('id'), threading.current_thread().name,threading.current_thread().ident, Utils.str(msg)), level)

    @staticmethod
    def translate_path(path):
        import xbmcvfs
        return xbmcvfs.translatePath(path)
    
    @staticmethod
    def to_kodi_item_date_str(dt):
        s = None
        if dt:
            s = '%02d.%02d.%04d' % (dt.day, dt.month, dt.year,)
        return s
    
    @staticmethod
    def to_db_date_str(dt):
        s = None
        if dt:
            s = '%04d-%02d-%02d %02d:%02d:%02d' % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        return s
    
    @staticmethod
    def to_datetime(s):
        import datetime
        import re
        try:
            # datetime.fromisoformat is documented to accept three or six
            # fractional-second digits. Graph emits seven for some
            # SharePoint-backed items, and the bare handler below would
            # swallow that and silently drop the list item's date rather
            # than report it. Truncate to six first; the substitution is a
            # no-op for every value with six digits or fewer, so this is not
            # redundant with the handler and must not be removed as such.
            s = re.sub(r'(\.\d{6})\d+', r'\1', s)
            return datetime.datetime.fromisoformat(s)
        except:
            return None
        
    @staticmethod
    def to_timestamp(s):
        dt = KodiUtils.to_datetime(s)
        if dt:
            dt = int(time.mktime(dt.timetuple()))
        return dt
    
    @staticmethod
    def file(f, opts="r"):
        import xbmcvfs
        return xbmcvfs.File(f, opts)
    
    @staticmethod
    def file_exists(f):
        import xbmcvfs
        return xbmcvfs.exists(f)
    
    @staticmethod
    def file_delete(f):
        import xbmcvfs
        return xbmcvfs.delete(f)
    
    @staticmethod
    def file_rename(f, newFile):
        import xbmcvfs
        return xbmcvfs.rename(f, newFile)
    
    @staticmethod
    def mkdir(f):
        import xbmcvfs
        return xbmcvfs.mkdir(f)
    
    @staticmethod
    def mkdirs(f):
        import xbmcvfs
        return xbmcvfs.mkdirs(f)
    
    @staticmethod
    def rmdir(f, force=False):
        import xbmcvfs
        return xbmcvfs.rmdir(f, force)
    
    @staticmethod
    def read_content_file(file_path):
        content = None
        f = None
        try:
            f = KodiUtils.file(file_path, 'r')
            content = f.read()
        finally:
            if f:
                f.close()
        return content

    @staticmethod
    def kodi_player_class():
        import xbmc
        return xbmc.Player
    
    @staticmethod
    def get_info_label(label):
        import xbmc
        return xbmc.getInfoLabel(label)
    
    @staticmethod
    def get_current_library_info():
        dbtype = KodiUtils.get_info_label('ListItem.DBTYPE')
        dbid = KodiUtils.get_info_label('ListItem.DBID')
        path = KodiUtils.get_info_label('ListItem.FileNameAndPath')
        if path:
            return {'type': dbtype, 'id': dbid, 'path': path}
    
    @staticmethod
    def find_video_in_library(itemtype, item_id, filename):
        KodiUtils.log('find_video_in_library - %s - %s - %s' % (itemtype, item_id, filename), KodiUtils.LOGDEBUG)
        db = itemtype + 's'
        params = {'properties':['file'], 'filter': {"field": "filename", "operator": "contains", "value": filename}}
        response = KodiUtils.execute_json_rpc('videolibrary.get' + db, params)
        if response['result']['limits']['total'] > 0:
            collection = response['result'][db]
            for video in collection:
                path = video['file']
                content = KodiUtils.read_content_file(path)
                if content:
                    params = urllib.parse.parse_qs(urllib.parse.urlparse(content).query)
                    if 'item_id' in params:
                        if params['item_id'][0] == item_id:
                            KodiUtils.log('FOUND!', KodiUtils.LOGDEBUG)
                            return {'type': itemtype, 'id': video[itemtype+'id'], 'path': path}

    @staticmethod
    def find_exported_video_in_library(item_id, filename):
        info = KodiUtils.find_video_in_library('episode', item_id, filename)
        if not info:
            info = KodiUtils.find_video_in_library('movie', item_id, filename)
        return info
    
    @staticmethod
    def get_video_details(itemtype, dbid):
        params = {'properties':['resume','playcount'], itemtype + 'id': int(dbid)}
        key = itemtype + 'details'
        response = KodiUtils.execute_json_rpc('videolibrary.get' + key, params)
        if 'result' in response and key in response['result']:
            return response['result'][key]
    
    @staticmethod
    def save_video_details(itemtype, dbid, details):
        details[itemtype + 'id'] = int(dbid)
        key = itemtype + 'details'
        return KodiUtils.execute_json_rpc('videolibrary.set' + key, details)
    
    @staticmethod
    def get_home_property(key):
        win = KodiUtils.get_window(KodiUtils.HOME_WINDOW)
        value = win.getProperty(key)
        del win
        return value
    
    @staticmethod
    def set_home_property(key, value):
        win = KodiUtils.get_window(KodiUtils.HOME_WINDOW)
        win.setProperty(key, value)
        del win
    
    @staticmethod
    def clear_home_property(key):
        win = KodiUtils.get_window(KodiUtils.HOME_WINDOW)
        win.clearProperty(key)
        del win
