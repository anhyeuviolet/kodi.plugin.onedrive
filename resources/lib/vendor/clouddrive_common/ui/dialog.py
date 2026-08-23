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

import xbmcgui, xbmcvfs
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
from resources.lib.vendor.clouddrive_common.utils import Utils
import os
from resources.lib.vendor.clouddrive_common.export import ExportManager
# urllib.parse, not bare urllib: importing the package alone does not bind the
# submodule, so the urllib.parse.unquote calls further down have only ever
# resolved because some other module imported it first.
import urllib.parse
import uuid

class DialogProgressBG (xbmcgui.DialogProgressBG):
    _default_heading = None
    created = False
    
    def __init__(self, default_heading):
        self._default_heading = default_heading
                 
    def create(self, heading, message=None):
        if self.created:
            self.update(heading=heading, message=message)
        else:
            super(DialogProgressBG, self).create(heading, message)
            self.created = True
    
    def close(self):
        if self.created:
            super(DialogProgressBG, self).close()
            self.created = False
    
    def update(self, percent=0, heading=None, message=None):
        if not self.created:
            if not heading: heading = self._default_heading
            self.create(heading=heading, message=message)
        if percent < 0: percent = 0
        if percent > 100: percent = 100
        super(DialogProgressBG, self).update(percent=int(percent), heading=heading, message=message)
    
    def iscanceled(self):
        if self.created:
            return super(DialogProgress, self).iscanceled()
        return False 
    
class DialogProgress (xbmcgui.DialogProgress):
    _default_heading = None
    created = False
    
    def __init__(self, default_heading):
        self._default_heading = default_heading
        
    def create(self, heading, line1="", line2="", line3=""):
        if self.created:
            self.close()
        if line2:
            line1 += line2
        if line3:
            line1 += line3
        super(DialogProgress, self).create(heading, line1)
        self.created = True
    
    def close(self):
        if self.created:
            super(DialogProgress, self).close()
            self.created = False
    
    def update(self, percent, line1="", line2="", line3=""):
        if not self.created:
            self.create(self._default_heading, line1, line2, line3)
        if percent < 0: percent = 0
        if percent > 100: percent = 100
        if line2:
            line1 += line2
        if line3:
            line1 += line3
        super(DialogProgress, self).update(int(percent), line1)
        
    def iscanceled(self):
        if self.created:
            return super(DialogProgress, self).iscanceled()
        return False 
        
        
class QRDialogProgress(xbmcgui.WindowXMLDialog):
    _heading_control = 1000
    _qr_control = 1001
    _text_control = 1002
    _cancel_btn_control = 1003
    _new_code_btn_control = 1004
    _code_control = 1005

    # Catalogue ids for the words this dialog owns. The words themselves live
    # in resources/language/, so they exist in one place and can be translated.
    _countdown_string_id = 30038
    _expired_string_id = 30039
    _new_code_string_id = 30040

    def __init__(self, *args, **kwargs):
        self.heading = kwargs["heading"]
        self.qr_code = kwargs["qr_code"]
        self.line1 = kwargs["line1"]
        self.line2 = kwargs["line2"]
        self.line3 = kwargs["line3"]
        # Optional, so the existing caller keeps working unchanged. The flow
        # that fills it in lands separately; between the two commits the
        # add-on still has to run.
        self.code = kwargs.get("code", "")
        self.percent = 0
        self._image_path = None
        self.canceled = False
        self.expired = False
        self.new_code_requested = False

    def __del__(self):
        # The image path is unset until onInit has run, and a dialog that is
        # constructed and then abandoned before that - which is exactly what
        # an immediate abort produces - used to call delete with None right
        # here, inside a destructor, where the interpreter discards the error
        # and prints a note nobody reads. getattr rather than the attribute
        # itself, because __init__ may not have completed either.
        image_path = getattr(self, "_image_path", None)
        if image_path:
            xbmcvfs.delete(image_path)

    @staticmethod
    def create(heading, qr_code, line1="", line2="", line3="", code=""):
        return QRDialogProgress("pin-dialog.xml", KodiUtils.get_common_addon_path(), "default", heading=heading, qr_code=qr_code, line1=line1, line2=line2, line3=line3, code=code)

    def iscanceled(self):
        return self.canceled

    def is_new_code_requested(self):
        return self.new_code_requested

    @staticmethod
    def _addon_string(string_id, fallback):
        # Deliberately not KodiUtils.localize: that sends every id below 32000
        # to xbmc.getLocalizedString, which reads Kodi's own catalogue. This
        # add-on's ids sit in the 30000 block Kodi reserves for plugins, so
        # they have to be read from the add-on itself.
        try:
            text = KodiUtils.get_common_addon().getLocalizedString(string_id)
        except Exception:
            text = None
        return text or fallback

    @staticmethod
    def _is_secure_url(value):
        try:
            parsed = urllib.parse.urlparse(Utils.str(value))
        except Exception:
            return False
        return parsed.scheme == "https" and bool(parsed.netloc)

    def onInit(self):
        self.getControl(self._heading_control).setLabel(self.heading)
        self.set_code(self.code)
        new_code_button = self.getControl(self._new_code_btn_control)
        new_code_button.setLabel(self._addon_string(self._new_code_string_id, "Get a new code"))
        # Hidden until the code expires. Hidden from here rather than by a
        # visible condition in the XML, because a condition in the XML wins
        # over setVisible the next time it is evaluated.
        new_code_button.setVisible(False)
        # A QR is a thing a person is instructed to point a camera at, and the
        # address inside it is the one the provider returned - never one built
        # locally. The value arrives over TLS so the real protection is the
        # transport, but asserting the scheme costs one line, and refusing
        # leaves the code on screen rather than taking the whole dialog down.
        if self._is_secure_url(self.qr_code):
            import resources.lib.vendor.pyqrcode as pyqrcode
            profile_path = Utils.unicode(KodiUtils.translate_path(KodiUtils.get_addon_info("profile")))
            # A brand-new add-on id means a brand-new addon_data directory, which
            # may not exist on first sign-in; without this the write raises before
            # the dialog renders. Upstream never needed it: its profile always existed.
            KodiUtils.mkdirs(profile_path)
            # Kodi's texture cache is keyed by path, so one fixed name lets a second
            # sign-in within the same session render the previous image against the
            # new code - a dialog that looks right showing a code that will not
            # authorise. A per-invocation name makes the question moot.
            self._image_path = os.path.join(profile_path, "qr-%s.png" % uuid.uuid4().hex)
            qrcode = pyqrcode.create(Utils.str(self.qr_code))
            qrcode.png(self._image_path, scale=10)
            del qrcode
            self.getControl(self._qr_control).setImage(self._image_path)
        else:
            from resources.lib.vendor.clouddrive_common.ui.logger import Logger
            Logger.error("QRDialogProgress: refusing to encode a sign-in address that is not an https URL")
        self.update(self.percent, self.line1, self.line2, self.line3)
        # Focus is set once, here. It used to be the last line of update(),
        # which a countdown calls once a second: that returns focus to Cancel
        # every tick, so no focus the flow sets anywhere else can survive.
        self.setFocus(self.getControl(self._cancel_btn_control))

    def _render_text(self):
        text = self.line1
        if self.line2:
            text = text + "[CR]" + self.line2
        if self.line3:
            text = text + "[CR]" + self.line3
        self.getControl(self._text_control).setText(text)

    def update(self, percent, line1="", line2="", line3=""):
        self.percent = percent
        if percent < 0: percent = 0
        if percent > 100: percent = 100
        if line1:
            self.line1 = line1
        if line2:
            self.line2 = line2
        if line3:
            self.line3 = line3
        self._render_text()
        # No setFocus here, ever. See onInit.

    def set_code(self, code):
        """Put the code in the code control and nowhere else."""
        self.code = code
        self.getControl(self._code_control).setLabel(Utils.str(code or ""))

    @staticmethod
    def format_remaining(seconds):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 0
        if seconds < 0:
            seconds = 0
        return "%d:%02d" % (seconds // 60, seconds % 60)

    def set_remaining(self, seconds):
        """Write the countdown line and touch nothing else.

        Driven by the caller once a second. It needs no thread: show() is
        non-blocking, so the poll loop already ticks at that rate, and a
        worker mutating controls while onInit may still be running is how the
        stuck-dialog class of bug is produced.
        """
        template = self._addon_string(self._countdown_string_id, "This code expires in %s")
        formatted = self.format_remaining(seconds)
        if "%s" in template:
            self.line3 = template % formatted
        else:
            self.line3 = "%s %s" % (template, formatted)
        self._render_text()

    def set_expired(self, message=None):
        """Show the second action, focus it exactly once, swap the body text.

        Cancel is left in place rather than hidden, so there are always two
        ways out of this dialog on a device whose only other escape is force
        -stopping Kodi. The guard is what makes "exactly once" structural: a
        caller that discovers expiry on every tick still moves focus once.
        """
        if self.expired:
            return
        self.expired = True
        self.line1 = message or self._addon_string(self._expired_string_id, "This code has expired.")
        self.line2 = ""
        self.line3 = ""
        self._render_text()
        button = self.getControl(self._new_code_btn_control)
        button.setVisible(True)
        self.setFocus(button)

    def reset_for_new_code(self, line1="", line2="", line3=""):
        """Return to the live state once the caller has a fresh code.

        The caller re-reads the expiry from the new response rather than
        reusing the previous one: the provider randomises it, and three
        observed runs differed.
        """
        self.new_code_requested = False
        if not self.expired:
            return
        self.expired = False
        self.line1 = line1
        self.line2 = line2
        self.line3 = line3
        self._render_text()
        button = self.getControl(self._new_code_btn_control)
        button.setVisible(False)
        # Focus has to move: it is sitting on a control about to disappear.
        # This is a transition, not a tick.
        self.setFocus(self.getControl(self._cancel_btn_control))

    def onClick(self, control_id):
        if control_id == self._cancel_btn_control:
            self.canceled = True
            self.close()
        elif control_id == self._new_code_btn_control:
            # Reported, not acted on. This dialog does not own the protocol,
            # and a dialog that makes network calls is the thing that later
            # becomes impossible to test.
            self.new_code_requested = True

    def onAction(self, action):
        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            self.canceled = True
        super(QRDialogProgress, self).onAction(action)
        
class ExportScheduleDialog(xbmcgui.WindowXMLDialog):
    _daily_type = 32082
    _startup_type = 32081
    
    def __init__(self, *args, **kwargs):
        self._common_addon = KodiUtils.get_common_addon()
        self._dialog = xbmcgui.Dialog()
        self.canceled = False
        self._schedule_types = [ExportScheduleDialog._startup_type,self._daily_type,17,11,12,13,14,15,16]
        self._schedule_ats = []
        for hour in range(0,24):
            self._schedule_ats.append('%02d:00' % hour)
        self.schedule = Utils.default(kwargs["schedule"], {'type': self._daily_type, 'at' : self._schedule_ats[0]})
        
    def __del__(self):
        del self._common_addon
        del self._dialog

    @staticmethod
    def create(schedule=None):
        return ExportScheduleDialog("export-schedule-dialog.xml", KodiUtils.get_common_addon_path(), "default", schedule=schedule)
    
    def iscanceled(self):
        return self.canceled
    
    def onInit(self):
        self.title_label = self.getControl(1000)
        self.cancel_button = self.getControl(1002)
        self.save_button = self.getControl(1003)
        self.schedule_type_button = self.getControl(1011)
        self.schedule_at_label = self.getControl(10100)
        self.schedule_at_button = self.getControl(1012)
        self.title_label.setLabel(self._common_addon.getLocalizedString(32083))
        self.setFocus(self.save_button)
        self.setFocus(self.schedule_type_button)
        self.schedule_type_button.setLabel(KodiUtils.localize(self.schedule['type'], addon=self._common_addon))
        self.schedule_at_button.setLabel(self.schedule['at']) 
        self.schedule_at_label.setLabel(KodiUtils.localize(32080, addon=self._common_addon))
        self.check_schedule_type()
    
    def check_schedule_type(self):
        visible = self.schedule['type'] != self._startup_type
        self.at_visible(visible)
        if not visible:
            self.schedule['at'] = self._schedule_ats[0]
            self.schedule_at_button.setLabel(self.schedule['at']) 
            
    def at_visible(self, visible):
        self.schedule_at_label.setVisible(visible)
        self.schedule_at_button.setVisible(visible)
        
    def onClick(self, control_id):
        if control_id == self.cancel_button.getId():
            self.canceled = True
            self.close()
        elif control_id == self.schedule_type_button.getId():
            options = []
            preselect = self._schedule_types.index(self.schedule['type'])
            for schedule_type in self._schedule_types:
                options.append(KodiUtils.localize(schedule_type, addon=self._common_addon))
            title = KodiUtils.localize(32079, addon=self._common_addon) + '...'
            self.schedule['type'] = self._schedule_types[self._dialog.select(title, options, preselect=preselect)]
            self.schedule_type_button.setLabel(KodiUtils.localize(self.schedule['type'], addon=self._common_addon))
            self.check_schedule_type() 
        elif control_id == self.schedule_at_button.getId():
            title = KodiUtils.localize(32079, addon=self._common_addon) + ' ' + KodiUtils.localize(self.schedule['type'], addon=self._common_addon) + ' ' + KodiUtils.localize(32080, addon=self._common_addon) + '...'
            self.schedule['at'] = self._schedule_ats[self._dialog.select(title, self._schedule_ats, preselect=self._schedule_ats.index(self.schedule['at']))]
            self.schedule_at_button.setLabel(self.schedule['at']) 
        elif control_id == self.save_button.getId():
            self.close()
            
    
    def onAction(self, action):
        
        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            self.canceled = True
        super(ExportScheduleDialog, self).onAction(action)
        
class ExportMainDialog(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.content_type = urllib.parse.unquote(kwargs["content_type"])
        self.driveid = kwargs["driveid"]
        self.item_driveid = kwargs["item_driveid"]
        self.item_id = kwargs["item_id"]
        self.name = urllib.parse.unquote(kwargs["name"])
        self.account_manager = kwargs["account_manager"]
        self.provider = kwargs["provider"]
        self.provider.configure(self.account_manager, self.driveid)
        self.export_manager = ExportManager(self.account_manager.db._base_path)
        self._addon_name = KodiUtils.get_addon_info('name')
        self._common_addon = KodiUtils.get_common_addon()
        self._dialog = xbmcgui.Dialog()
        self.editing = False
        self.canceled = False
        self.run = False
        self.schedules = []
        
    def __del__(self):
        del self._common_addon
        del self._dialog

    @staticmethod
    def create(content_type, driveid, item_driveid, item_id, name, account_manager, provider):
        return ExportMainDialog("export-main-dialog.xml", KodiUtils.get_common_addon_path(), "default", content_type=content_type, driveid=driveid, item_driveid=item_driveid, item_id=item_id, name=name, account_manager=account_manager, provider=provider)
    
    def iscanceled(self):
        return self.canceled
    
    def onInit(self):
        self.title_label = self.getControl(1000)
        self.cancel_button = self.getControl(999)
        self.save_button = self.getControl(1001)
        self.save_export_button = self.getControl(1002)
        
        self.drive_name_label = self.getControl(1003)
        self.drive_folder_label = self.getControl(1004)
        self.dest_folder_label = self.getControl(1005)
        self.dest_folder_button = self.getControl(1006)
        
        self.update_library_sw = self.getControl(1007)
        self.download_artwork_sw = self.getControl(1008)
        self.watch_drive_sw = self.getControl(1009)
        self.schedule_sw = self.getControl(1010)
        
        self.schedule_label = self.getControl(10100)
        self.schedule_list = self.getControl(1011)
        self.add_schedule_button = self.getControl(1012)
        self.setFocus(self.dest_folder_button)
        
        self.schedule_label.setLabel(self._common_addon.getLocalizedString(32083))
        
        self.title_label.setLabel(self._addon_name + ' - ' + self._common_addon.getLocalizedString(32004))
        account = self.account_manager.get_by_driveid('account', self.driveid)
        drive = self.account_manager.get_by_driveid('drive', self.driveid, account)
        drive_name = self.account_manager.get_account_display_name(account, drive, self.provider, True)
        self.drive_name_label.setLabel(drive_name)
        self.drive_folder_label.setLabel(self.name)
        
        exports = self.export_manager.get_exports()
        export = Utils.get_safe_value(exports, self.item_id, {})
        if export:
            self.editing = True
            self.watch_drive_sw.setSelected(Utils.get_safe_value(export, 'watch', False))
            self.download_artwork_sw.setSelected(Utils.get_safe_value(export, 'download_artwork', False))
            self.schedule_sw.setSelected(Utils.get_safe_value(export, 'schedule', False))
            self.update_library_sw.setSelected(Utils.get_safe_value(export, 'update_library', False))
            self.schedules = Utils.get_safe_value(export, 'schedules', [])
            for schedule in self.schedules:
                self.add_schedule_item(schedule)
        
        if not self.editing:
            self.select_detination()
        else:
            self.dest_folder_label.setLabel(Utils.get_safe_value(export, 'destination_folder', ''))
        self.schedule_enabled(self.schedule_sw.isSelected())
        
    def is_valid_export(self):
        if not self.dest_folder_label.getLabel():
            self._dialog.ok(self._addon_name, KodiUtils.localize(32084,addon=self._common_addon) % KodiUtils.localize(32085,addon=self._common_addon))
            return False
        return True
    
    def save_export(self):
        self.export_manager.save_export({
            'id': self.item_id,
            'item_driveid': self.item_driveid,
            'driveid': self.driveid,
            'name': self.name,
            'content_type': self.content_type,
            'destination_folder': self.dest_folder_label.getLabel(),
            'watch': self.watch_drive_sw.isSelected(),
            'download_artwork':self.download_artwork_sw.isSelected(),
            'schedule': self.schedule_sw.isSelected(),
            'update_library': self.update_library_sw.isSelected(),
            'schedules': self.schedules,
            'run_immediately': self.run
        })
    
    def schedule_enabled(self, enabled):
        self.schedule_label.setEnabled(enabled)
        self.schedule_list.setEnabled(enabled)
        self.add_schedule_button.setEnabled(enabled)
    
    def select_detination(self, default=''):
        dest_folder = self._dialog.browse(0, self._common_addon.getLocalizedString(32002), 'files', defaultt=default)
        self.dest_folder_label.setLabel(dest_folder)
            
    def add_schedule_item(self, schedule):
        list_item = xbmcgui.ListItem(self.get_schedule_statement(schedule))
        self.schedule_list.addItem(list_item)
        
    def get_schedule_statement(self, schedule):
        statement = self._common_addon.getLocalizedString(32079) + ' ' + KodiUtils.localize(schedule['type'], addon=self._common_addon)
        if schedule['type'] != ExportScheduleDialog._startup_type:
            statement = statement + ' ' + self._common_addon.getLocalizedString(32080) + ' ' + schedule['at']
        return statement
    
    def edit_selected_schedule(self):
        schedule = None
        editing = -1
        if self.getFocusId() == self.schedule_list.getId():
            editing = self.schedule_list.getSelectedPosition()
            schedule = self.schedules[editing]
        schedule_dialog = ExportScheduleDialog.create(schedule)
        schedule_dialog.doModal()
        if not schedule_dialog.iscanceled():
            valid = True
            if editing >= 0:
                schedule = schedule_dialog.schedule
                self.schedules[editing] = schedule
                self.schedule_list.getListItem(editing).setLabel(self.get_schedule_statement(schedule))
            else:
                for schedule in self.schedules:
                    if schedule['type'] == schedule_dialog.schedule['type'] and schedule['at'] == schedule_dialog.schedule['at']:
                        valid = False
                        break
                if valid:
                    self.schedules.append(schedule_dialog.schedule)
                    self.add_schedule_item(schedule_dialog.schedule)
    
    def delete_selected_schedule(self):
        if self.getFocusId() == self.schedule_list.getId():
            index = self.schedule_list.getSelectedPosition()
            self.schedule_list.removeItem(index)
            self.schedules.remove(self.schedules[index])
    
    def onClick(self, control_id):
        if control_id == self.cancel_button.getId():
            self.canceled = True
            self.close()
        elif control_id == self.save_button.getId() or control_id == self.save_export_button.getId():
            if self.is_valid_export():
                self.run = control_id == self.save_export_button.getId()
                self.save_export()
                self.close()
                
        elif control_id == self.dest_folder_button.getId():
            self.select_detination(self.dest_folder_label.getLabel())
        elif control_id == self.schedule_sw.getId():
            self.schedule_enabled(self.schedule_sw.isSelected())
        elif control_id == self.schedule_list.getId() or control_id == self.add_schedule_button.getId():
            self.edit_selected_schedule()
    
    def onAction(self, action):
        
        if action.getId() == xbmcgui.ACTION_PREVIOUS_MENU or action.getId() == xbmcgui.ACTION_NAV_BACK:
            self.canceled = True
        elif action.getId() == xbmcgui.ACTION_CONTEXT_MENU:
            if self.getFocusId() == self.schedule_list.getId():
                index = self._dialog.contextmenu(['Edit...', 'Delete'])
                if index == 0:
                    self.edit_selected_schedule()
                elif index == 1:
                    self.delete_selected_schedule()
        super(ExportMainDialog, self).onAction(action)
        

