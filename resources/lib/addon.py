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

import urllib

from resources.lib.vendor.clouddrive_common.ui.addon import CloudDriveAddon
from resources.lib.vendor.clouddrive_common.utils import Utils
from resources.lib.provider.onedrive import OneDrive

class OneDriveAddon(CloudDriveAddon):
    _provider = OneDrive()
    _action = None
    
    def __init__(self):
        super(OneDriveAddon, self).__init__()
        
    def get_provider(self):
        return self._provider
    
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

