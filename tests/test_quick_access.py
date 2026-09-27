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
"""Quick access: fewer steps from the add-on to a video, and a library in one step.

The decisions live in `resources/lib/quickaccess.py` and are tested here without
Kodi. The listing and the actions live in `resources/lib/addon.py` and are driven
through `tests/kodistub.py`, because what matters about them is what the listing
contains and what gets written, not what the source text says.
"""

import json
import os
import urllib.parse
from urllib.error import HTTPError

import pytest

from kodistub import kodi_stubs
from resources.lib import quickaccess


def _params(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


def _actions(items):
    return [_params(item[0]).get('action') for item in items]


# ---------------------------------------------------------------------------
# single_drive
# ---------------------------------------------------------------------------

def _account(drives, **extra):
    account = {'id': 'a', 'drives': drives}
    account.update(extra)
    return account


def test_one_account_with_one_drive_is_opened_directly():
    drive = {'id': 'd1'}
    assert quickaccess.single_drive({'a': _account([drive])}) is drive


@pytest.mark.parametrize('accounts', [
    {},
    None,
    {'a': _account([{'id': 'd1'}]), 'b': _account([{'id': 'd2'}])},
    {'a': _account([])},
    {'a': _account([{'id': 'd1'}, {'id': 'd2'}])},
    {'a': _account([{'name': 'no id'}])},
])
def test_anything_else_keeps_the_account_list(accounts):
    assert quickaccess.single_drive(accounts) is None


def test_an_account_waiting_to_sign_in_again_keeps_its_row():
    accounts = {'a': _account([{'id': 'd1'}], needs_reauth=True)}
    assert quickaccess.single_drive(
        accounts, lambda account: account.get('needs_reauth')) is None


# ---------------------------------------------------------------------------
# Start folders
# ---------------------------------------------------------------------------

def test_a_start_folder_round_trips_per_drive_and_content_type(tmp_path):
    profile = str(tmp_path / 'profile')
    quickaccess.set_start_folder(profile, 'd1', 'video', 'd1', 'F1', 'Phim')
    quickaccess.set_start_folder(profile, 'd1', 'audio', 'd1', 'F2', 'Nhạc')

    assert quickaccess.get_start_folder(profile, 'd1', 'video') == {
        'item_driveid': 'd1', 'item_id': 'F1', 'name': 'Phim'}
    assert quickaccess.get_start_folder(profile, 'd1', 'audio')['name'] == 'Nhạc'
    assert quickaccess.get_start_folder(profile, 'd2', 'video') is None

    assert quickaccess.clear_start_folder(profile, 'd1', 'video') is True
    assert quickaccess.get_start_folder(profile, 'd1', 'video') is None
    assert quickaccess.get_start_folder(profile, 'd1', 'audio') is not None
    assert quickaccess.clear_start_folder(profile, 'd1', 'video') is False


@pytest.mark.parametrize('content', [
    '{not json', '[]', '{"d1": "x"}', '{"d1": {"video": {"item_id": ""}}}'])
def test_a_damaged_store_reads_as_no_start_folder(tmp_path, content):
    (tmp_path / quickaccess.START_FOLDERS_FILE).write_text(content)
    assert quickaccess.get_start_folder(str(tmp_path), 'd1', 'video') is None


def test_the_store_is_replaced_whole(tmp_path):
    quickaccess.set_start_folder(str(tmp_path), 'd1', 'video', 'd1', 'F1', 'x')
    assert os.listdir(str(tmp_path)) == [quickaccess.START_FOLDERS_FILE]
    with open(str(tmp_path / quickaccess.START_FOLDERS_FILE)) as f:
        assert json.load(f)['d1']['video']['item_id'] == 'F1'


# ---------------------------------------------------------------------------
# Library plan
# ---------------------------------------------------------------------------

ROOT = os.path.join('lib')


def _plan(exports=None, name='Phim bộ', kind='tvshows', exists=lambda p: False):
    return quickaccess.plan_library_export(
        exports or {}, ROOT, kind, 'd1', 'd1', 'F1', name, exists)


def test_a_new_folder_becomes_a_watched_export_into_its_kind():
    export, refusal = _plan()
    assert refusal is None
    assert export['id'] == 'F1'
    assert export['name'] == 'Phim bộ'
    assert export['destination_folder'] == os.path.join(ROOT, 'tvshows')
    assert export['content_type'] == 'video'
    assert export['watch'] and export['update_library'] and export['run_immediately']


def test_movies_and_tv_shows_are_separate_folders():
    assert (quickaccess.library_destination(ROOT, 'movies')
            != quickaccess.library_destination(ROOT, 'tvshows'))


def test_an_exported_folder_is_not_exported_twice():
    assert _plan(exports={'F1': {'id': 'F1'}}) == (None, quickaccess.ALREADY_EXPORTED)


def test_two_folders_with_one_name_cannot_share_a_library_folder():
    other = {'id': 'F9', 'name': 'PHIM BỘ',
             'destination_folder': os.path.join(ROOT, 'tvshows', '')}
    assert _plan(exports={'F9': other}) == (None, quickaccess.NAME_TAKEN)
    # The same name under the other kind is a different folder on disk.
    assert _plan(exports={'F9': other}, kind='movies')[1] is None


def test_a_folder_already_on_disk_is_never_taken_over():
    """The export service empties an existing destination folder by default."""
    seen = []

    def exists(path):
        seen.append(path)
        return True

    assert _plan(exists=exists) == (None, quickaccess.FOLDER_EXISTS)
    assert seen == [os.path.join(ROOT, 'tvshows', 'Phim bộ')]


@pytest.mark.parametrize('name', ['', '  ', '.', '..', 'a/b', 'a\\b', '../x'])
def test_a_name_that_is_not_one_folder_is_refused(name):
    assert _plan(name=name) == (None, quickaccess.INVALID_NAME)


def test_an_unknown_kind_is_refused():
    assert _plan(kind='music') == (None, quickaccess.UNKNOWN_KIND)


# ---------------------------------------------------------------------------
# The add-on, driven
# ---------------------------------------------------------------------------

class _Dialog(object):
    def __init__(self):
        self.shown = []

    def ok(self, heading, message):
        self.shown.append(('ok', message))
        return True

    def yesno(self, heading, message, *args, **kwargs):
        self.shown.append(('yesno', message))
        return False

    # What select() answers; None means "keep what was preselected".
    choice = None

    def select(self, heading, options, preselect=-1, **kwargs):
        self.shown.append(('select', heading, preselect))
        return preselect if self.choice is None else self.choice


class _AccountManager(object):
    def __init__(self, accounts):
        self.accounts = accounts

    def get_by_driveid(self, kind, driveid, account=None):
        for account in self.accounts.values():
            for drive in account['drives']:
                if drive['id'] == driveid:
                    return account if kind == 'account' else drive
        raise LookupError(driveid)


def _one_account(**extra):
    account = {'id': 'account-1',
               'drives': [{'id': 'drive-1', 'display_name': 'Kenny',
                           'type': 'personal'}]}
    account.update(extra)
    return {'account-1': account}


def _addon(tmp_path, accounts=None, content_type='video', settings=None):
    from resources.lib.addon import OneDriveAddon
    import xbmcaddon

    xbmcaddon.Addon.settings.update(settings or {})
    # The sentences that carry a placeholder, so formatting them is exercised.
    xbmcaddon.Addon.strings.update({
        30086: 'added; add %s as %s', 30088: 'taken: %s', 30089: 'exists: %s',
        30097: 'registered; see %s', 30100: 'what is in %s?'})
    addon = object.__new__(OneDriveAddon)
    addon._addon = xbmcaddon.Addon()
    addon._common_addon = xbmcaddon.Addon()
    addon._addon_name = 'OneDrive KN'
    addon._addon_url = 'plugin://plugin.onedrive.kn/'
    addon._addon_handle = 1
    addon._addon_params = {}
    addon._content_type = content_type
    addon._profile_path = str(tmp_path / 'profile')
    accounts = _one_account() if accounts is None else accounts
    addon._account_manager = _AccountManager(accounts)
    addon.get_accounts = lambda with_format=False: accounts
    addon._dialog = _Dialog()
    for unused in ('_progress_dialog', '_progress_dialog_bg',
                   '_system_monitor'):
        setattr(addon, unused, None)
    addon.cancel_operation = lambda: False
    addon.listed = []

    def list_folder(driveid, item_driveid=None, item_id=None, path=None):
        addon.listed.append((driveid, item_driveid, item_id, path))
    addon._list_folder = list_folder
    return addon


def _quiet_notifications(monkeypatch):
    from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
    shown = []
    monkeypatch.setattr(KodiUtils, 'show_notification',
                        staticmethod(lambda msg, time=5000: shown.append(msg)))
    return shown


def test_the_only_account_opens_on_its_folders(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        addon.list_accounts()

        assert addon.listed == [('drive-1', None, None, '/')], (
            'one account should open straight on the root of its drive')
        actions = _actions(recorder.directory_items)
        # What only the account list offered stays one row away.
        assert '_list_accounts' in actions
        assert '_add_account' not in actions
        assert '_search' in actions and '_list_exports' in actions
        for _, item, is_folder in recorder.directory_items:
            assert item.properties.get('SpecialSort') == 'top'
        # A 401 while listing must still be able to name the drive.
        assert addon._addon_params['driveid'] == 'drive-1'


def test_the_full_account_list_is_still_reachable(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        addon._list_accounts()
        assert '_add_account' in _actions(recorder.directory_items)
        assert addon.listed == []


@pytest.mark.parametrize('accounts, settings', [
    (_one_account(needs_reauth=True), {}),
    (_one_account(), {'skip_single_account': 'false'}),
])
def test_the_account_list_is_kept_when_it_is_needed_or_wanted(
        tmp_path, accounts, settings):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path, accounts=accounts, settings=settings)
        addon.list_accounts()
        assert addon.listed == []
        assert '_add_account' in _actions(recorder.directory_items)


def test_the_old_drive_menu_comes_back_when_merging_is_off(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path, settings={'merge_drive_menu': 'false'})
        addon._list_drive('drive-1')
        assert addon.listed == []
        labels = [item.label for _, item, _ in recorder.directory_items]
        assert labels[0] == '[B]string-32052[/B]'


def test_a_start_folder_replaces_the_root(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        quickaccess.set_start_folder(addon._profile_path, 'drive-1', 'video',
                                     'drive-1', 'F1', 'Phim')
        addon._list_drive('drive-1')

        assert addon.listed == [('drive-1', 'drive-1', 'F1', None)]
        rows = recorder.directory_items
        all_files = [(url, item) for url, item, _ in rows
                     if _params(url).get('path') == '/']
        assert len(all_files) == 1, 'the root must stay one row away'
        reset = [cmd for _, cmd in all_files[0][1].context_items]
        assert any('_clear_start_folder' in cmd for cmd in reset)


def test_a_start_folder_that_is_gone_falls_back_to_the_root(tmp_path, monkeypatch):
    shown = _quiet_notifications(monkeypatch)
    with kodi_stubs(tmp_path / 'p'):
        addon = _addon(tmp_path)
        quickaccess.set_start_folder(addon._profile_path, 'drive-1', 'video',
                                     'drive-1', 'GONE', 'Phim')

        def list_folder(driveid, item_driveid=None, item_id=None, path=None):
            addon.listed.append((driveid, item_driveid, item_id, path))
            if item_id == 'GONE':
                raise HTTPError('u', 404, 'Not Found', {}, None)
        addon._list_folder = list_folder
        addon._list_drive('drive-1')

        assert addon.listed[-1] == ('drive-1', None, None, '/')
        assert quickaccess.get_start_folder(
            addon._profile_path, 'drive-1', 'video') is None
        assert shown == ['string-30082']


def test_any_other_failure_is_not_mistaken_for_a_missing_folder(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon = _addon(tmp_path)
        quickaccess.set_start_folder(addon._profile_path, 'drive-1', 'video',
                                     'drive-1', 'F1', 'Phim')

        def list_folder(driveid, item_driveid=None, item_id=None, path=None):
            raise HTTPError('u', 503, 'Unavailable', {}, None)
        addon._list_folder = list_folder
        with pytest.raises(HTTPError):
            addon._list_drive('drive-1')
        assert quickaccess.get_start_folder(
            addon._profile_path, 'drive-1', 'video') is not None


def test_folders_offer_start_folder_and_library_and_files_do_not(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcgui
        addon = _addon(tmp_path)
        params = {'content_type': 'video', 'driveid': 'drive-1',
                  'item_driveid': 'drive-1', 'item_id': 'F1'}
        folder = addon.get_context_options(xbmcgui.ListItem('Phim'),
                                           dict(params), True)
        actions = [_params(cmd[cmd.index('(') + 1:-1]).get('action')
                   for _, cmd in folder]
        assert actions == ['_set_start_folder', '_latest_videos',
                           '_add_to_favourites', '_create_playlist',
                           '_add_to_library', '_add_to_library']
        # Opened in place, so Back returns to the folder list.
        assert folder[1][1].startswith('Container.Update(')
        assert _params(folder[0][1][len('RunPlugin('):-1])['name'] == 'Phim'
        assert addon.get_context_options(xbmcgui.ListItem('a.mkv'),
                                         dict(params), False) == []

        addon._content_type = 'image'
        image = addon.get_context_options(xbmcgui.ListItem('Anh'),
                                          dict(params), True)
        assert len(image) == 1, 'the library is for videos only'


def test_video_listings_declare_their_content(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        addon._process_items([], 'drive-1')
        assert recorder.content == 'videos'
        assert recorder.end_of_directory is True


class _Provider(object):
    def __init__(self, item):
        self.item = item
        self.asked = []

    def configure(self, account_manager, driveid):
        pass

    def get_item(self, item_driveid=None, item_id=None, **kwargs):
        self.asked.append((item_driveid, item_id))
        return self.item


def _library_addon(tmp_path, item):
    addon = _addon(tmp_path)
    provider = _Provider(item)
    addon.get_provider = lambda: provider
    return addon, provider


def _exports(addon):
    from resources.lib.vendor.clouddrive_common.export import ExportManager
    return ExportManager(addon._profile_path).get_exports()


def test_adding_to_the_library_takes_the_name_from_onedrive(tmp_path, monkeypatch):
    _quiet_notifications(monkeypatch)
    with kodi_stubs(tmp_path / 'p'):
        addon, provider = _library_addon(
            tmp_path, {'id': 'F1', 'name': 'Phim bộ', 'folder': {}})
        os.makedirs(addon._profile_path)
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'tvshows')

        assert provider.asked == [('drive-1', 'F1')]
        export = _exports(addon)['F1']
        destination = os.path.join(addon._profile_path, 'library', 'tvshows')
        assert export['name'] == 'Phim bộ'
        assert export['destination_folder'] == destination
        assert os.path.isdir(destination), (
            'the folder must exist before the user is asked to add it as a source')
        # One show or several: asked, with the guess preselected.
        assert addon._dialog.shown[0] == ('select', 'what is in Phim bộ?', 0)
        # No video database to write in the stub: the one-time instructions.
        assert destination in addon._dialog.shown[-1][1]


def test_a_file_is_not_added_to_the_library(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, _ = _library_addon(tmp_path, {'id': 'F1', 'name': 'a.mkv'})
        os.makedirs(addon._profile_path)
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'movies')
        assert _exports(addon) == {}
        assert addon._dialog.shown == [('ok', 'string-30090')]


def test_an_existing_folder_in_the_library_is_left_alone(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, _ = _library_addon(
            tmp_path, {'id': 'F1', 'name': 'Phim', 'folder': {}})
        mine = os.path.join(addon._profile_path, 'library', 'movies', 'Phim')
        os.makedirs(mine)
        open(os.path.join(mine, 'keep.txt'), 'w').close()
        addon._add_to_library('drive-1', 'drive-1', 'F1', 'movies')

        assert _exports(addon) == {}
        assert os.path.exists(os.path.join(mine, 'keep.txt'))
        assert addon._dialog.shown == [('ok', 'exists: Phim')]


def test_an_unknown_kind_does_nothing(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, provider = _library_addon(
            tmp_path, {'id': 'F1', 'name': 'Phim', 'folder': {}})
        addon._add_to_library('drive-1', 'drive-1', 'F1', '../../etc')
        assert provider.asked == []


def test_a_widget_logs_a_failure_instead_of_raising_a_dialog(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        addon._quiet = True
        addon._addonid = 'plugin.onedrive.kn'
        addon._addon_version = addon._common_addon_version = '1'
        addon._handle_exception(HTTPError('u', 500, 'boom', {}, None))
        assert addon._dialog.shown == []
        assert isinstance(addon._dialog, _Dialog), 'the real dialog is restored'
        assert recorder.end_of_directory is False


# ---------------------------------------------------------------------------
# Latest videos
# ---------------------------------------------------------------------------

def _tree():
    """root -> a.mkv, Show/ -> S1/ -> e1.mkv, e2.mkv ; Show/deep/ -> ..."""
    return {
        'root': [{'id': 'a', 'name': 'a.mkv', 'last_modified_date': '2026-01-01T00:00:00Z'},
                 {'id': 'show', 'name': 'Show', 'folder': {}},
                 {'id': 'n', 'name': 'notes.txt', 'last_modified_date': '2026-09-01T00:00:00Z'}],
        'show': [{'id': 's1', 'name': 'S1', 'folder': {}},
                 {'id': 'nodate', 'name': 'x.mkv'}],
        's1': [{'id': 'e1', 'name': 'e1.mkv', 'last_modified_date': '2026-03-01T00:00:00Z'},
               {'id': 'e2', 'name': 'e2.mkv', 'last_modified_date': '2026-05-01T10:00:00Z'},
               {'id': 'deeper', 'name': 'Extras', 'folder': {}}],
        'deeper': [{'id': 'too-deep', 'name': 'z.mkv', 'last_modified_date': '2027-01-01T00:00:00Z'}],
    }


def _walk(**kwargs):
    tree = _tree()
    listed = []

    def children(folder):
        key = 'root' if folder == 'ROOT' else folder['id']
        listed.append(key)
        return tree.get(key, [])
    videos = quickaccess.newest_videos(
        children, 'ROOT', lambda item: item['name'].endswith('.mkv'), **kwargs)
    return [v['id'] for v in videos], listed


def test_latest_videos_are_newest_first_and_skip_other_files():
    ids, listed = _walk()
    assert ids == ['e2', 'e1', 'a', 'nodate']
    assert 'deeper' not in listed, 'two levels below the folder, no further'


def test_latest_videos_respect_the_listing_cap_and_the_limit():
    ids, listed = _walk(max_listings=2)
    assert listed == ['root', 'show']
    assert _walk(limit=1)[0] == ['e2']


def test_the_latest_listing_opens_newest_first(tmp_path, monkeypatch):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcplugin
        added = []
        monkeypatch.setattr(xbmcplugin, 'addSortMethod',
                            lambda handle, sortMethod: added.append(sortMethod))
        addon = _addon(tmp_path)
        addon._addon_params = {'action': '_latest_videos'}
        addon._add_sort_methods()
        assert added[0] == xbmcplugin.SORT_METHOD_UNSORTED
        added.clear()
        addon._addon_params = {'action': '_list_folder'}
        addon._add_sort_methods()
        assert added[0] == xbmcplugin.SORT_METHOD_LABEL, 'other listings unchanged'


def test_latest_videos_walks_folders_through_the_provider(tmp_path):
    tree = _tree()

    class Provider(object):
        def configure(self, account_manager, driveid):
            pass

        def get_folder_items(self, item_driveid=None, item_id=None, path=None,
                             on_items_page_completed=None):
            items = tree['root' if path == '/' else item_id]
            return [dict(i, name_extension=i['name'].rsplit('.', 1)[-1]) for i in items]

    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path, settings={'browse_cache_minutes': '0'})
        addon.get_provider = lambda: Provider()
        addon._video_file_extensions = ['mkv']
        shown = []
        addon._process_items = lambda items, driveid: shown.extend(
            i['id'] for i in items)
        addon._latest_videos('drive-1', path='/')
        assert shown == ['e2', 'e1', 'a', 'nodate']


def test_the_home_screen_offers_latest_videos_for_the_start_folder(tmp_path):
    with kodi_stubs(tmp_path / 'p') as recorder:
        addon = _addon(tmp_path)
        quickaccess.set_start_folder(addon._profile_path, 'drive-1', 'video',
                                     'drive-1', 'F1', 'Phim')
        addon._list_drive('drive-1')
        latest = [_params(url) for url, _, _ in recorder.directory_items
                  if _params(url).get('action') == '_latest_videos']
        assert latest and latest[0]['item_id'] == 'F1'


# ---------------------------------------------------------------------------
# Folder listing cache
# ---------------------------------------------------------------------------

def test_cache_keys_cover_folders_and_skip_changing_lists():
    key = quickaccess.listing_cache_key
    assert key('d', 'd', 'F1', None, 'M') is not None
    assert key('d', None, None, '/', 'M') is not None
    assert key('d', None, None, 'recent', 'M') is None
    assert key('d', None, None, 'sharedWithMe', 'M') is None
    assert key('d', 'd', 'F1', None, 'M') != key('d', 'd', 'F1', None, 'L')
    assert key('d', 'd', 'F1', None, 'M') != key('d2', 'd', 'F1', None, 'M')


class _MemoryCache(object):
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)


class _CountingProvider(object):
    def __init__(self):
        self.calls = 0

    def configure(self, account_manager, driveid):
        pass

    def get_folder_items(self, item_driveid=None, item_id=None, path=None,
                         on_items_page_completed=None):
        self.calls += 1
        return [{'id': 'v%d' % self.calls, 'name': 'v.mkv'}]


def _cached_addon(tmp_path):
    from resources.lib.addon import OneDriveAddon
    addon = _addon(tmp_path)
    del addon._list_folder                    # the real one, this time
    provider = _CountingProvider()
    cache = _MemoryCache()
    addon.get_provider = lambda: provider
    addon._listing_cache = lambda: cache
    addon._child_count_supported = False
    addon._process_items = lambda items, driveid: addon.listed.append(
        [i['id'] for i in items])
    return addon, provider, cache


def test_a_folder_opened_again_is_drawn_from_the_cache(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, provider, cache = _cached_addon(tmp_path)
        addon._list_folder('drive-1', 'drive-1', 'F1')
        addon._list_folder('drive-1', 'drive-1', 'F1')
        assert provider.calls == 1
        assert addon.listed == [['v1'], ['v1']]


def test_refresh_drops_the_cached_listing(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, provider, cache = _cached_addon(tmp_path)
        addon._list_folder('drive-1', 'drive-1', 'F1')
        addon._refresh_listing('drive-1', 'drive-1', 'F1', '')
        addon._list_folder('drive-1', 'drive-1', 'F1')
        assert provider.calls == 2
        assert addon.listed[-1] == ['v2']


def test_a_cancelled_listing_is_not_cached(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon, provider, cache = _cached_addon(tmp_path)
        addon.cancel_operation = lambda: True
        addon._list_folder('drive-1', 'drive-1', 'F1')
        assert cache.data == {} and addon.listed == []


def test_every_row_offers_to_refresh_the_folder_it_is_in(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        import xbmcgui
        addon = _addon(tmp_path)
        addon._current_listing = {'driveid': 'drive-1', 'item_driveid': 'drive-1',
                                  'item_id': 'PARENT', 'path': ''}
        options = addon.get_context_options(xbmcgui.ListItem('a.mkv'),
                                            {'item_id': 'CHILD'}, False)
        refresh = _params(options[0][1][len('RunPlugin('):-1])
        assert refresh['action'] == '_refresh_listing'
        assert refresh['item_id'] == 'PARENT'


def test_a_cache_time_of_zero_turns_the_cache_off(tmp_path):
    with kodi_stubs(tmp_path / 'p'):
        addon = _addon(tmp_path, settings={'browse_cache_minutes': '0'})
        addon._addonid = 'plugin.onedrive.kn'
        assert addon._listing_cache() is None


# ---------------------------------------------------------------------------
# Sharper thumbnails
# ---------------------------------------------------------------------------

def test_sharper_thumbnails_prefer_the_large_size():
    from resources.lib.graph import items as graph_items
    entry = {'id': 'x', 'name': 'a.mkv',
             'thumbnails': [{'medium': {'url': 'M'}, 'large': {'url': 'L'}}]}
    assert graph_items.extract_item(entry)['thumbnail'] == 'M'
    assert graph_items.extract_item(
        entry, thumbnail_preference=graph_items.LARGE_THUMBNAIL_PREFERENCE
    )['thumbnail'] == 'L'
