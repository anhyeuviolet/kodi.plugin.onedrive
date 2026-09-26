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

import os
import urllib.parse
from urllib.error import HTTPError

import datetime

from resources.lib import quickaccess
from resources.lib.graph import items as graph_items
from resources.lib.vendor.clouddrive_common.cache.cache import Cache
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils
from resources.lib.vendor.clouddrive_common.export import ExportManager
from resources.lib.vendor.clouddrive_common.ui.addon import CloudDriveAddon
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
from resources.lib.vendor.clouddrive_common.utils import Utils
from resources.lib.provider.onedrive import OneDrive


class _SilentDialog(object):
    """Stands in for xbmcgui.Dialog while a widget reports a failure.

    A widget is drawn on the home screen with nobody asking for it, so a failure
    there is logged and not shown: a modal dialog over the home screen, raised
    by a row the user never selected, is worse than an empty widget. Every
    question is answered no, which is the answer that changes nothing.
    """

    def ok(self, *args, **kwargs):
        return True

    def yesno(self, *args, **kwargs):
        return False

    def notification(self, *args, **kwargs):
        return None

class OneDriveAddon(CloudDriveAddon):
    _provider = OneDrive()
    _action = None
    # True when this invocation fills a widget rather than a window somebody
    # opened. Class-level so an instance built without __init__ reads False.
    _quiet = False
    _large_thumbnails = False
    _current_listing = None
    
    def __init__(self):
        super(OneDriveAddon, self).__init__()
        self._quiet = self._running_as_widget()
        if self._quiet or self._setting_on('fast_listing'):
            # The count only feeds the progress bar, and it costs one request
            # to Graph before every listing.
            self._child_count_supported = False
        self._large_thumbnails = self._setting_on('large_thumbnails', False)
        self._provider.thumbnail_preference = (
            graph_items.LARGE_THUMBNAIL_PREFERENCE if self._large_thumbnails
            else graph_items.THUMBNAIL_PREFERENCE)
        # The folder whose listing is being built, so each row can offer to
        # refresh it. Set by _list_folder.
        self._current_listing = None

    def _add_sort_methods(self):
        if Utils.get_safe_value(self._addon_params, 'action') == '_latest_videos':
            # Newest first is the whole point of that listing, and Kodi opens
            # a listing in the order of the first sort method it was given.
            import xbmcplugin
            for method in (xbmcplugin.SORT_METHOD_UNSORTED,
                           xbmcplugin.SORT_METHOD_DATE,
                           xbmcplugin.SORT_METHOD_LABEL,
                           xbmcplugin.SORT_METHOD_SIZE):
                xbmcplugin.addSortMethod(handle=self._addon_handle,
                                         sortMethod=method)
            return
        super(OneDriveAddon, self)._add_sort_methods()
        
    def get_provider(self):
        return self._provider

    # ------------------------------------------------------------------
    # Quick access: fewer steps from the add-on to a video.
    # ------------------------------------------------------------------

    def _setting_on(self, setting_id, default=True):
        # '' is what Kodi answers for a setting that was never stored, which is
        # every new setting on an existing installation until its screen is
        # saved once. That must read as the declared default, not as off.
        value = self._addon.getSetting(setting_id)
        if value == '':
            return default
        return value == 'true'

    @staticmethod
    def _running_as_widget():
        # A listing opened by a person runs inside one of the media windows
        # (Videos, Music, Pictures, Programs). A home-screen widget runs with
        # the home window active instead.
        import xbmc
        return not xbmc.getCondVisibility('Window.IsMedia')

    def _url(self, params):
        return self._addon_url + '?' + urllib.parse.urlencode(params)

    def _run_plugin(self, params):
        return 'RunPlugin(' + self._url(params) + ')'

    def list_accounts(self):
        if self._setting_on('skip_single_account'):
            drive = quickaccess.single_drive(self.get_accounts(),
                                             self._needs_reauthorisation)
            if drive:
                self._home(drive['id'], skipped_accounts=True)
                return
        super(OneDriveAddon, self).list_accounts()

    def _list_accounts(self):
        """The full account list, reachable after it was skipped.

        Skipping the list must not lose what only the list offers: adding a
        second account, signing in again and removing an account.
        """
        super(OneDriveAddon, self).list_accounts()

    def _list_drive(self, driveid):
        if self._setting_on('merge_drive_menu'):
            self._home(driveid)
        else:
            super(OneDriveAddon, self)._list_drive(driveid)

    def _home(self, driveid, skipped_accounts=False):
        """The drive's first screen: its folders, with the shortcuts on top.

        Before, the first screen was a menu whose first row led to the folders,
        so every visit cost one extra step. The menu's rows are kept, pinned to
        the top of the same listing.
        """
        import xbmcplugin
        # The failure handler reads the drive from the address to offer signing
        # in again, and an address that skipped the account list names none.
        if isinstance(self._addon_params, dict):
            self._addon_params.setdefault('driveid', driveid)
        start = quickaccess.get_start_folder(self._profile_path, driveid,
                                             self._content_type)
        rows = self._home_rows(driveid, start, skipped_accounts)
        xbmcplugin.addDirectoryItems(self._addon_handle, rows, len(rows))
        if start:
            try:
                self._list_folder(driveid, item_driveid=start['item_driveid'],
                                  item_id=start['item_id'])
                return
            except Exception as ex:
                httpex = ExceptionUtils.extract_exception(ex, HTTPError)
                if httpex is None or httpex.code != 404:
                    raise
                # Deleted or moved out of reach on OneDrive. Forget it and fall
                # back to the root, rather than leaving a first screen that can
                # only ever show an error.
                Logger.notice('start folder %s is gone; forgetting it'
                              % start['item_id'])
                quickaccess.clear_start_folder(self._profile_path, driveid,
                                               self._content_type)
                if not self._quiet:
                    KodiUtils.show_notification(self._addon_string(30082))
        self._list_folder(driveid, path='/')

    def _home_rows(self, driveid, start, skipped_accounts):
        import xbmcgui
        rows = []
        content_type = self._content_type

        def add(label, params, context_options=None):
            list_item = xbmcgui.ListItem('[B]%s[/B]' % Utils.unicode(label))
            # Kept above the folders whatever sort order the user picks.
            list_item.setProperty('SpecialSort', 'top')
            if context_options:
                list_item.addContextMenuItems(context_options)
            rows.append((self._url(params), list_item, True))

        if start:
            add(self._addon_string(30091),
                {'action': '_list_folder', 'path': '/',
                 'content_type': content_type, 'driveid': driveid},
                [(self._addon_string(30079), self._run_plugin(
                    {'action': '_clear_start_folder',
                     'content_type': content_type, 'driveid': driveid}))])
        for folder in self.get_custom_drive_folders(driveid) or []:
            params = {'action': '_list_folder', 'path': folder['path'],
                      'content_type': content_type, 'driveid': driveid}
            if 'params' in folder:
                params.update(folder['params'])
            add(folder['name'], params, folder.get('context_options'))
        if content_type == 'video':
            latest = {'action': '_latest_videos', 'content_type': content_type,
                      'driveid': driveid}
            if start:
                latest['item_driveid'] = start['item_driveid']
                latest['item_id'] = start['item_id']
            else:
                latest['path'] = '/'
            add(self._addon_string(30092), latest)
        if content_type in ('video', 'audio'):
            add(self._common_addon.getLocalizedString(32000),
                {'action': '_list_exports', 'content_type': content_type,
                 'driveid': driveid})
        add(self._common_addon.getLocalizedString(32039),
            {'action': '_search', 'content_type': content_type,
             'driveid': driveid})
        if skipped_accounts:
            add(self._addon_string(30077),
                {'action': '_list_accounts', 'content_type': content_type})
        return rows

    # ------------------------------------------------------------------
    # Folder listing cache
    # ------------------------------------------------------------------

    LISTING_CACHE = 'listing'

    def _listing_cache(self):
        try:
            minutes = int(self._addon.getSetting('browse_cache_minutes') or 30)
        except ValueError:
            minutes = 30
        if minutes <= 0:
            return None
        return Cache(self._addonid, self.LISTING_CACHE,
                     datetime.timedelta(minutes=minutes))

    def _listing_key(self, driveid, item_driveid, item_id, path):
        return quickaccess.listing_cache_key(
            driveid, item_driveid, item_id, path,
            'L' if self._large_thumbnails else 'M')

    def _folder_items(self, driveid, item_driveid=None, item_id=None,
                      path=None, progress=True):
        """A folder's items, from the listing cache when it holds them.

        None when the listing was cancelled. The vendored listing asked OneDrive
        on every visit; a folder opened again within the cache time is now
        drawn without a network round trip.
        """
        provider = self.get_provider()
        provider.configure(self._account_manager, driveid)
        cache = self._listing_cache()
        key = self._listing_key(driveid, item_driveid, item_id, path)
        if cache and key:
            items = cache.get(key)
            if isinstance(items, list):
                return items
        if progress and self._child_count_supported:
            item = provider.get_item(item_driveid, item_id, path)
            if item:
                self._load_target = Utils.get_safe_value(
                    Utils.get_safe_value(item, 'folder', {}), 'child_count', 0)
                self._progress_dialog_bg.create(
                    self._addon_name,
                    self._common_addon.getLocalizedString(32049)
                    % Utils.str(self._load_target))
        items = provider.get_folder_items(
            item_driveid, item_id, path,
            on_items_page_completed=(self.on_items_page_completed
                                     if progress else None))
        if self.cancel_operation():
            return None
        if cache and key:
            try:
                cache.set(key, items)
            except (TypeError, ValueError) as ex:
                # A listing that cannot be stored is still a listing.
                Logger.debug('listing not cached: %s' % Utils.str(ex))
        return items

    def _list_folder(self, driveid, item_driveid=None, item_id=None, path=None):
        items = self._folder_items(driveid, item_driveid, item_id, path)
        if items is None:
            return
        self._current_listing = {
            'driveid': driveid, 'item_driveid': item_driveid or '',
            'item_id': item_id or '', 'path': path or ''}
        self._process_items(items, driveid)

    def _refresh_listing(self, driveid, item_driveid=None, item_id=None,
                         path=None):
        cache = self._listing_cache()
        key = self._listing_key(driveid, item_driveid or None, item_id or None,
                                path or None)
        if cache and key:
            cache.remove(key)
        KodiUtils.executebuiltin('Container.Refresh')

    def _clear_cache(self):
        super(OneDriveAddon, self)._clear_cache()
        Cache(self._addonid, self.LISTING_CACHE, 0).clear()

    def _latest_videos(self, driveid, item_driveid=None, item_id=None,
                       path=None):
        """The newest videos in a folder and the folders below it."""
        root = {'item_driveid': item_driveid, 'id': item_id, 'path': path}

        def list_children(folder):
            if folder is root:
                items = self._folder_items(driveid, item_driveid, item_id,
                                           path, progress=False)
            else:
                items = self._folder_items(
                    driveid,
                    Utils.default(Utils.get_safe_value(folder, 'drive_id'),
                                  item_driveid or driveid),
                    folder.get('id'), progress=False)
            return items or []

        extensions = self._video_file_extensions

        def is_video(item):
            return 'video' in item or item.get('name_extension') in extensions

        self.get_provider().configure(self._account_manager, driveid)
        videos = quickaccess.newest_videos(list_children, root, is_video)
        if self.cancel_operation():
            return
        self._process_items(videos, driveid)

    def _process_items(self, items, driveid):
        if self._content_type == 'video':
            # Lets the skin offer its video views (poster, wall, info) on the
            # add-on's folders, as it does in the library.
            import xbmcplugin
            xbmcplugin.setContent(self._addon_handle, 'videos')
        super(OneDriveAddon, self)._process_items(items, driveid)

    def on_items_page_completed(self, items):
        if self._quiet:
            return
        super(OneDriveAddon, self).on_items_page_completed(items)

    def get_context_options(self, list_item, params, is_folder):
        options = super(OneDriveAddon, self).get_context_options(
            list_item, params, is_folder)
        if self._current_listing:
            refresh = {'action': '_refresh_listing',
                       'content_type': self._content_type}
            refresh.update(self._current_listing)
            options.append((self._addon_string(30093),
                            self._run_plugin(refresh)))
        if not is_folder or not params.get('item_id'):
            return options
        content_type = self._content_type
        driveid = params.get('driveid')
        item_driveid = params.get('item_driveid') or driveid
        item_id = params['item_id']
        options.append((self._addon_string(30078), self._run_plugin(
            {'action': '_set_start_folder', 'content_type': content_type,
             'driveid': driveid, 'item_driveid': item_driveid,
             'item_id': item_id, 'name': Utils.str(list_item.getLabel())})))
        if content_type == 'video':
            latest = {'action': '_latest_videos', 'content_type': content_type,
                      'driveid': driveid, 'item_driveid': item_driveid,
                      'item_id': item_id}
            options.append((self._addon_string(30092),
                            'Container.Update(%s)' % self._url(latest)))
            for kind, string_id in (('movies', 30083), ('tvshows', 30084)):
                options.append((self._addon_string(string_id), self._run_plugin(
                    {'action': '_add_to_library', 'content_type': content_type,
                     'driveid': driveid, 'item_driveid': item_driveid,
                     'item_id': item_id, 'kind': kind})))
        return options

    def _set_start_folder(self, driveid, item_driveid, item_id, name=None):
        # Only the drive's own account list can have produced `driveid`; one
        # that no stored account holds is refused here, before anything is
        # written, by the same lookup every other action makes.
        self._account_manager.get_by_driveid('drive', driveid)
        quickaccess.set_start_folder(self._profile_path, driveid,
                                     self._content_type, item_driveid, item_id,
                                     Utils.unicode(name or ''))
        KodiUtils.show_notification(self._addon_string(30080)
                                    % Utils.unicode(name or item_id))

    def _clear_start_folder(self, driveid):
        quickaccess.clear_start_folder(self._profile_path, driveid,
                                       self._content_type)
        KodiUtils.show_notification(self._addon_string(30081))
        KodiUtils.executebuiltin('Container.Refresh')

    def _library_root(self):
        configured = Utils.unicode(self._addon.getSetting('library_folder') or '')
        if configured:
            return Utils.unicode(KodiUtils.translate_path(configured))
        return os.path.join(self._profile_path, 'library')

    def _add_to_library(self, driveid, item_driveid, item_id, kind):
        """Export a folder as .strm files into a library folder, in one step.

        The name written to disk is read from OneDrive, never from the address:
        the export service joins it onto the library folder, and removing the
        export can delete that path, so a name taken from a plugin address
        anyone can construct would be a path anyone could choose.
        """
        if kind not in quickaccess.LIBRARY_KINDS:
            return
        provider = self.get_provider()
        provider.configure(self._account_manager, driveid)
        item = provider.get_item(item_driveid, item_id)
        if not item or 'folder' not in item:
            self._dialog.ok(self._addon_name, self._addon_string(30090))
            return
        name = Utils.unicode(item['name'])
        root = self._library_root()
        destination = quickaccess.library_destination(root, kind)
        first_of_kind = not KodiUtils.file_exists(os.path.join(destination, ''))
        export_manager = ExportManager(self._profile_path)
        export, refusal = quickaccess.plan_library_export(
            export_manager.get_exports(), root, kind, driveid,
            Utils.default(Utils.get_safe_value(item, 'drive_id'), item_driveid),
            item['id'], name,
            lambda path: (KodiUtils.file_exists(path)
                          or KodiUtils.file_exists(os.path.join(path, ''))))
        if refusal:
            if refusal == quickaccess.ALREADY_EXPORTED:
                message = self._addon_string(30087)
            elif refusal == quickaccess.NAME_TAKEN:
                message = self._addon_string(30088) % name
            elif refusal == quickaccess.FOLDER_EXISTS:
                message = self._addon_string(30089) % name
            else:
                message = self._addon_string(30090)
            self._dialog.ok(self._addon_name, message)
            return
        if first_of_kind:
            KodiUtils.mkdirs(os.path.join(destination, ''))
        export_manager.save_export(export)
        if first_of_kind:
            content = KodiUtils.localize(342 if kind == 'movies' else 20343)
            self._dialog.ok(self._addon_name, self._addon_string(30086)
                            % (destination, content))
        else:
            KodiUtils.show_notification(self._addon_string(30085))

    def _handle_exception(self, ex, show_error_dialog=True):
        if not self._quiet:
            super(OneDriveAddon, self)._handle_exception(ex, show_error_dialog)
            return
        dialog = self._dialog
        self._dialog = _SilentDialog()
        try:
            super(OneDriveAddon, self)._handle_exception(ex, False)
        finally:
            self._dialog = dialog
        # A widget waits on its listing; close it as failed so the skin stops
        # waiting. An action run with RunPlugin has no listing (handle -1).
        if self._addon_handle is not None and self._addon_handle >= 0:
            import xbmcplugin
            xbmcplugin.endOfDirectory(self._addon_handle, succeeded=False)
    
    def get_custom_drive_folders(self, driveid):
        drive = self._account_manager.get_by_driveid('drive', driveid)
        drive_folders = []
        if drive['type'] == 'personal':
            if self._content_type == 'image':
                path = 'special/photos'
                params = {'action': '_slideshow', 'content_type': self._content_type, 'driveid': driveid, 'path': path}
                context_options = [(self._common_addon.getLocalizedString(32032), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')')]
                drive_folders.append({'name' : self._addon.getLocalizedString(30007), 'path' : path, 'context_options': context_options})
                
                path = 'special/cameraroll'
                params['path'] = path
                context_options = [(self._common_addon.getLocalizedString(32032), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')')]
                drive_folders.append({'name' : self._addon.getLocalizedString(30008), 'path' : path, 'context_options': context_options})
            elif self._content_type == 'audio':
                drive_folders.append({'name' : self._addon.getLocalizedString(30009), 'path' : 'special/music'})
        drive_folders.append({'name' : self._common_addon.getLocalizedString(32053), 'path' : 'recent'})
        if drive['type'] != 'documentLibrary':
            drive_folders.append({'name' : self._common_addon.getLocalizedString(32058), 'path' : 'sharedWithMe'})
        return drive_folders

    # ------------------------------------------------------------------
    # TEMPORARY DEBUG AFFORDANCE - vendor lift, not a feature.
    #
    # Why it exists: "every dialog opens" is one of the acceptance
    # conditions for the vendor lift, and QRDialogProgress is constructed
    # deep inside the sign-in flow, three lines after a call to a broker
    # that has been dead since November 2022. No amount of clicking
    # reaches it. Asserting that the skin XML files were copied proves the
    # copy but not the scriptPath argument, which is the thing that
    # actually breaks - so the dialogs have to be constructed for real.
    #
    # It lives in this repository's own file rather than in
    # resources/lib/vendor/ so that removing it is one contiguous block
    # here and never another local modification to a vendored file.
    # Everything it needs is imported inside the method for the same
    # reason. It is recorded in VENDORED.md and is scheduled for removal,
    # or for a debug-only gate, before release.
    #
    # Reachable as: plugin://plugin.onedrive.kn/?action=_dialog_smoke
    # ------------------------------------------------------------------
    def _dialog_smoke(self):
        import os
        import xbmc
        import xbmcplugin
        import xbmcvfs
        from resources.lib.vendor.clouddrive_common.export import ExportManager
        from resources.lib.vendor.clouddrive_common.ui.dialog import ExportMainDialog
        from resources.lib.vendor.clouddrive_common.ui.dialog import ExportScheduleDialog
        from resources.lib.vendor.clouddrive_common.ui.dialog import QRDialogProgress
        from resources.lib.vendor.clouddrive_common.ui.logger import Logger
        from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils

        def say(label, value):
            Logger.notice('dialog-smoke: %s: %s' % (label, value))

        def show(dialog, seconds=4):
            # show() rather than doModal(): the point is to prove the skin
            # resolves and the textures load, not to wait for a human.
            dialog.show()
            xbmc.sleep(int(seconds * 1000))
            dialog.close()
            xbmc.sleep(500)

        # The two paths the whole exercise is about: the directory Kodi is
        # asked to resolve the dialog XML under, and the directory the QR
        # image is written into. Both must name THIS add-on.
        skin_path = KodiUtils.get_common_addon_path()
        profile_path = Utils.unicode(KodiUtils.translate_path(self._addon.getAddonInfo('profile')))
        say('addon id', self._addonid)
        say('dialog scriptPath', skin_path)
        say('profile path', profile_path)

        # ---- QRDialogProgress, constructed twice on purpose -----------
        # Kodi's texture cache is keyed by path, so a fixed image filename
        # lets a second sign-in inside one session render the first image
        # against the second code. The vendored dialog now builds a
        # per-invocation name; two constructions logging two different
        # paths is what turns that from a claim into an observation.
        for attempt in (1, 2):
            try:
                qr = QRDialogProgress.create(
                    heading='Dialog smoke %d of 2' % attempt,
                    qr_code='https://example.invalid/dialog-smoke/%d' % attempt,
                    line1='Vendor lift dialog smoke test',
                    line2='This dialog closes by itself.',
                    line3='')
                qr.show()
                # onInit runs on the GUI thread; wait for it to have
                # written the image rather than assuming it has.
                for _ in range(40):
                    if qr._image_path:
                        break
                    xbmc.sleep(100)
                xbmc.sleep(3000)
                image_path = qr._image_path
                say('QR image path %d of 2' % attempt, image_path)
                if image_path:
                    say('QR image exists %d of 2' % attempt, xbmcvfs.exists(image_path))
                    # The dialog deletes its own image on teardown, so keep
                    # a copy under a stable name: the acceptance pass has to
                    # be able to look at the file, not just at the log line.
                    keep = os.path.join(profile_path, 'dialog-smoke-qr-%d.png' % attempt)
                    xbmcvfs.copy(image_path, keep)
                    say('QR image copy %d of 2' % attempt, keep)
                qr.close()
                xbmc.sleep(500)
                del qr
            except Exception as ex:
                # One failing dialog must not hide the state of the others.
                Logger.error('dialog-smoke: QRDialogProgress %d of 2 failed' % attempt)
                Logger.error(ex)

        # ---- ExportScheduleDialog ------------------------------------
        try:
            schedule_dialog = ExportScheduleDialog.create()
            say('ExportScheduleDialog scriptPath', skin_path)
            show(schedule_dialog)
            del schedule_dialog
        except Exception as ex:
            Logger.error('dialog-smoke: ExportScheduleDialog failed')
            Logger.error(ex)

        # ---- ExportMainDialog ----------------------------------------
        # Its onInit reads an export out of a store and, finding none,
        # opens a modal folder browser that waits for a human. So the
        # smoke run gives it a throwaway store of its own with one record
        # already in it, and stubs for the two collaborators it only ever
        # asks for a display name. Nothing here touches the real account
        # store and nothing here makes a network call.
        smoke_path = os.path.join(profile_path, 'dialog-smoke')
        try:
            KodiUtils.mkdirs(smoke_path)
            item_id = 'dialog-smoke-item'
            ExportManager(smoke_path).save_export({
                'id': item_id,
                'name': 'Dialog smoke folder',
                'destination_folder': smoke_path,
                'content_type': 'video',
                'driveid': 'dialog-smoke-drive',
                'item_driveid': 'dialog-smoke-drive',
                'item_id': item_id,
                'watch': False,
                'download_artwork': False,
                'schedule': False,
                'update_library': False,
                'schedules': [],
            })

            class _SmokeDb(object):
                def __init__(self, base_path):
                    self._base_path = base_path

            class _SmokeAccountManager(object):
                def __init__(self, base_path):
                    self.db = _SmokeDb(base_path)

                def get_by_driveid(self, kind, driveid, account=None):
                    return {'id': driveid, 'name': 'Dialog smoke',
                            'type': 'personal', 'drives': []}

                def get_account_display_name(self, account, drive=None,
                                             provider=None, with_format=False):
                    return 'Dialog smoke account'

            class _SmokeProvider(object):
                def configure(self, account_manager, driveid):
                    return

            main_dialog = ExportMainDialog.create(
                'video', 'dialog-smoke-drive', 'dialog-smoke-drive', item_id,
                'Dialog smoke folder', _SmokeAccountManager(smoke_path),
                _SmokeProvider())
            say('ExportMainDialog scriptPath', skin_path)
            show(main_dialog)
            del main_dialog
        except Exception as ex:
            Logger.error('dialog-smoke: ExportMainDialog failed')
            Logger.error(ex)
        finally:
            try:
                # rmdir will not remove a directory that still has files in
                # it, and it reports that by returning False rather than by
                # raising - so empty it first, then remove it, and log what
                # the removal actually returned rather than assuming.
                for name in xbmcvfs.listdir(smoke_path)[1]:
                    xbmcvfs.delete(os.path.join(smoke_path, name))
                # Kodi's VFS wants a trailing separator before it will treat
                # the argument as a directory to remove.
                say('scratch store removed',
                    Utils.remove_folder(smoke_path + os.sep))
            except Exception as ex:
                Logger.error('dialog-smoke: could not remove %s' % smoke_path)
                Logger.error(ex)

        say('finished', 'all three dialogs attempted')
        if self._addon_handle is not None and self._addon_handle >= 0:
            xbmcplugin.endOfDirectory(self._addon_handle, succeeded=True,
                                      cacheToDisc=False)
    # ---------------- end temporary debug affordance -------------------

    def _action_map(self):
        """The base class's table, plus this add-on's own entries.

        `_dialog_smoke` is temporary and looks exactly like something to tidy
        away. It is also the only route to all three dialogs -- QRDialogProgress
        is built deep inside sign-in, and the two export dialogs need a store
        with a record already in it -- and the television acceptance pass
        repeats the phase-1 checklist through it. Removing this entry would fail
        nothing and would make that pass produce a green that meant nothing, so
        `test_the_dialog_affordance_stays_routable` holds it here until the
        affordance itself goes, in the same commit as the assertion.
        """
        actions = super(OneDriveAddon, self)._action_map()
        actions['_dialog_smoke'] = self._dialog_smoke
        actions['_list_accounts'] = self._list_accounts
        actions['_set_start_folder'] = self._set_start_folder
        actions['_clear_start_folder'] = self._clear_start_folder
        actions['_add_to_library'] = self._add_to_library
        actions['_latest_videos'] = self._latest_videos
        actions['_refresh_listing'] = self._refresh_listing
        return actions

    def _rename_action(self):
        if self._action == 'open_drive_folder':
            self._addon_params['path'] = Utils.get_safe_value(self._addon_params, 'folder')
        self._action = Utils.get_safe_value({
            'open_folder': '_list_folder',
            'open_drive': '_list_drive',
            'open_drive_folder': '_list_folder'
        }, self._action, self._action)

if __name__ == '__main__':
    OneDriveAddon().route()

