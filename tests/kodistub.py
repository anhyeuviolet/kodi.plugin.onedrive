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
"""Enough of the Kodi modules to import and drive the add-on's UI layer.

Why this exists. `resources/lib/auth/` has no Kodi in it and is tested without
any stub at all, which is the whole reason `tests/conftest.py` says it imports no
Kodi module. The UI layer is the opposite: `ui/addon.py` and `ui/dialog.py` are
Kodi from the first line, and the consequence measured during verification was
that a deliberate defect could be cut into either of them and the suite stayed
green -- the account list could lose its "Add an account..." row, and the QR
encoder could lose its refusal to encode a non-https address, with nothing going
red. Neither hole can be closed by reading source text: the first is about what
the listing *contains*, and the second is about whether an image is *produced*.
Both need the code run.

What this is not. It is not a Kodi emulator and must never grow into one. Every
class here is the smallest recorder that lets a real code path execute and then
answers one question about what it did. Where Kodi's own behaviour matters --
`xbmcvfs.mkdirs` really creating a directory, so the QR writer's first-sign-in
path is exercised -- it is implemented; everywhere else the stub records the call
and returns.

Isolation. `kodi_stubs()` is a context manager, and on exit it puts `sys.modules`
back exactly as it found it: the five fake Kodi modules are removed, and so is
every `resources.*` module imported while they were installed. Without that, a
vendored module imported here would keep a fake `xbmcgui` bound in its globals
for the rest of the session, and the next test file to import it would be testing
the stub. The restore is asserted rather than assumed -- see `_Restore.check`.
"""

import os
import sys
import types
from contextlib import contextmanager


KODI_MODULES = ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcplugin', 'xbmcvfs')


class Control(object):
    """A skin control, recording what was done to it.

    `image` and `text` start as None rather than '' on purpose: the QR test's
    question is whether `setImage` was called at all, and an empty string is a
    call that happened.
    """

    def __init__(self, control_id):
        self.control_id = control_id
        self.label = None
        self.text = None
        self.image = None
        self.visible = None

    def setLabel(self, label):
        self.label = label

    def setText(self, text):
        self.text = text

    def setImage(self, path):
        self.image = path

    def setVisible(self, visible):
        self.visible = visible


class ListItem(object):
    def __init__(self, label='', label2='', *args, **kwargs):
        self.label = label
        self.label2 = label2
        self.context_items = None
        self.properties = {}
        self.art = {}
        self.info = {}

    def addContextMenuItems(self, items, replaceItems=False):
        self.context_items = list(items)

    def setProperty(self, key, value):
        self.properties[key] = value

    def setArt(self, art):
        self.art.update(art)

    def setInfo(self, type, infoLabels):
        self.info.update(infoLabels)

    def getLabel(self):
        return self.label


class WindowXMLDialog(object):
    """The base class `QRDialogProgress` extends.

    Kodi's own constructor takes the xml name, the add-on path, the skin folder
    and the resolution positionally. The subclass under test overrides
    `__init__` and never chains, so accepting and discarding them is the whole
    contract this stub owes it.
    """

    def __init__(self, *args, **kwargs):
        pass

    def getControl(self, control_id):
        raise NotImplementedError(
            'a test driving a dialog must supply its own getControl; the stub '
            'base class deliberately has none, so a control that was never set '
            'up fails loudly rather than returning a silent do-nothing')

    def setFocus(self, control):
        self.focused = control

    def setFocusId(self, control_id):
        self.focused_id = control_id

    def show(self):
        pass

    def close(self):
        pass

    def doModal(self):
        pass


class Addon(object):
    """`xbmcaddon.Addon`, backed by two dictionaries.

    `getLocalizedString` returns a distinguishable placeholder for an id the
    test did not script, rather than '': a caller that renders an unscripted
    string then shows the id it asked for, which is readable in a failure
    message, where an empty label is indistinguishable from a missing call.
    """

    strings = {}
    info = {}
    settings = {}

    def __init__(self, id=None):
        self.id = id

    def getAddonInfo(self, info_id):
        return Addon.info.get(info_id, '')

    def getLocalizedString(self, string_id):
        return Addon.strings.get(string_id, 'string-%d' % string_id)

    def getSetting(self, setting_id):
        return Addon.settings.get(setting_id, '')

    def getSettingBool(self, setting_id):
        return bool(Addon.settings.get(setting_id, False))

    def setSetting(self, setting_id, value):
        Addon.settings[setting_id] = value


class _Recorder(object):
    """Somewhere for the module-level plugin calls to land."""

    def __init__(self):
        self.directory_items = None
        self.end_of_directory = None
        self.content = None


def _build_modules(profile_dir, addon_path, recorder):
    xbmc = types.ModuleType('xbmc')
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGNOTICE = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.log = lambda msg, level=0: None
    xbmc.getLocalizedString = lambda string_id: 'kodi-string-%d' % string_id
    xbmc.executebuiltin = lambda command, wait=False: None
    xbmc.getCondVisibility = lambda condition: False
    # Kodi's own answer, in Kodi's own format: a '|'-joined list of dotted
    # extensions. `CloudDriveAddon` calls this while its class body is being
    # evaluated, so importing the module at all depends on it.
    _SUPPORTED_MEDIA = {
        'video': '.m4v|.mp4|.mkv|.avi|.mov|.strm',
        'music': '.mp3|.flac|.m4a|.wav',
        'picture': '.jpg|.jpeg|.png|.gif',
    }
    xbmc.getSupportedMedia = lambda media_type: _SUPPORTED_MEDIA.get(
        media_type, '')

    class Monitor(object):
        def waitForAbort(self, timeout=0):
            return False

        def abortRequested(self):
            return False

    xbmc.Monitor = Monitor

    xbmcaddon = types.ModuleType('xbmcaddon')
    Addon.info = {'profile': profile_dir, 'path': addon_path,
                  'id': 'plugin.onedrive.kn', 'version': '1.0.0',
                  'name': 'OneDrive KN'}
    Addon.strings = {}
    Addon.settings = {}
    xbmcaddon.Addon = Addon

    xbmcgui = types.ModuleType('xbmcgui')
    xbmcgui.ListItem = ListItem
    xbmcgui.WindowXMLDialog = WindowXMLDialog
    xbmcgui.WindowXML = WindowXMLDialog
    xbmcgui.DialogProgressBG = object
    xbmcgui.DialogProgress = object
    xbmcgui.Dialog = object
    xbmcgui.Window = WindowXMLDialog
    xbmcgui.getCurrentWindowId = lambda: 10025
    xbmcgui.Control = Control

    xbmcplugin = types.ModuleType('xbmcplugin')

    def addDirectoryItems(handle, items, totalItems=0):
        recorder.directory_items = list(items)
        return True

    def endOfDirectory(handle, succeeded=True, updateListing=False,
                       cacheToDisc=True):
        recorder.end_of_directory = succeeded

    xbmcplugin.addDirectoryItems = addDirectoryItems
    xbmcplugin.endOfDirectory = endOfDirectory
    xbmcplugin.setContent = lambda handle, content: recorder.__setattr__(
        'content', content)
    xbmcplugin.addSortMethod = lambda *a, **k: None
    xbmcplugin.setPluginCategory = lambda *a, **k: None
    xbmcplugin.SORT_METHOD_NONE = 0
    xbmcplugin.SORT_METHOD_LABEL = 1
    xbmcplugin.SORT_METHOD_UNSORTED = 2

    xbmcvfs = types.ModuleType('xbmcvfs')
    xbmcvfs.translatePath = lambda path: path

    def mkdirs(path):
        # Really creates it. The QR writer's first-sign-in path exists because a
        # brand-new add-on id means a brand-new addon_data directory, and a stub
        # that returned True without creating anything would let the write that
        # follows fail in the test for a reason the device never has.
        try:
            os.makedirs(path)
        except OSError:
            return os.path.isdir(path)
        return True

    xbmcvfs.mkdirs = mkdirs
    xbmcvfs.exists = lambda path: os.path.exists(path)

    def delete(path):
        try:
            os.remove(path)
        except OSError:
            return False
        return True

    xbmcvfs.delete = delete

    return {'xbmc': xbmc, 'xbmcaddon': xbmcaddon, 'xbmcgui': xbmcgui,
            'xbmcplugin': xbmcplugin, 'xbmcvfs': xbmcvfs}


class _Restore(object):
    """Records `sys.modules` on the way in and puts it back on the way out.

    `check()` asserts the restore actually happened rather than trusting that it
    did. The failure this guards against is silent and it contaminates every
    later test in the session: a vendored module left in `sys.modules` keeps a
    fake `xbmcgui` bound in its globals, so the next importer gets the stub
    without asking for one.
    """

    def __init__(self):
        self.before_names = None
        self.saved = None

    def capture(self):
        self.before_names = set(sys.modules)
        self.saved = {name: sys.modules[name] for name in KODI_MODULES
                      if name in sys.modules}

    def restore(self):
        for name in list(sys.modules):
            if name in self.before_names:
                continue
            if name in KODI_MODULES or name.startswith('resources.'):
                del sys.modules[name]
        for name, module in self.saved.items():
            sys.modules[name] = module

    def check(self):
        leaked = sorted(name for name in sys.modules
                        if name not in self.before_names
                        and (name in KODI_MODULES
                             or name.startswith('resources.')))
        assert not leaked, (
            'the Kodi stub did not undo itself: %r are still in sys.modules '
            'after the context exited. Any later test importing one of them '
            'would get a module with a fake xbmc bound in its globals, and '
            'would be testing this stub rather than the add-on' % (leaked,))


@contextmanager
def kodi_stubs(profile_dir, addon_path=None):
    """Install the five fake Kodi modules, then take them out again.

    `profile_dir` is what `xbmcaddon.Addon().getAddonInfo('profile')` answers
    and therefore where the QR writer puts its image; pass a tmp_path. The
    directory need not exist -- not creating it is what exercises the writer's
    `mkdirs` call.
    """
    profile_dir = str(profile_dir)
    if addon_path is None:
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    recorder = _Recorder()
    restore = _Restore()
    restore.capture()
    modules = _build_modules(profile_dir, str(addon_path), recorder)
    sys.modules.update(modules)
    try:
        yield recorder
    finally:
        restore.restore()
        restore.check()
