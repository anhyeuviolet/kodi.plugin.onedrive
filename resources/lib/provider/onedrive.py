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

from resources.lib.auth import device_code
from resources.lib.graph import items as graph_items
from resources.lib.graph import pager as graph_pager
from resources.lib.graph import params as graph_params
from resources.lib.graph import paths as graph_paths
from resources.lib.vendor.clouddrive_common.remote.provider import Provider
from resources.lib.vendor.clouddrive_common.utils import Utils
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils

from urllib.error import HTTPError

class OneDrive(Provider):
    # No shared request-parameter dictionary. There used to be one here, as a
    # class attribute passed to every request, and search() wrote a filter into
    # it -- after which the next folder listing carried that filter and Graph
    # answered 400. Each call site now builds its own mapping through
    # graph.params. An instance attribute would not have been enough:
    # resources/lib/addon.py holds one provider as a class attribute of its own,
    # so every action in an invocation shares the instance, and service.py hands
    # this class to five services that share one interpreter for a whole Kodi
    # session (BROWSE-04).

    def __init__(self, source_mode = False):
        super(OneDrive, self).__init__('onedrive', source_mode)
        
    def _get_api_url(self):
        return 'https://graph.microsoft.com/v1.0'

    def _get_request_headers(self):
        return None
    
    def get_account(self, request_params=None, access_tokens=None):
        """The account's key and its label, without asking Graph who the user is.

        The profile endpoint documents User.Read as its least-privileged
        delegated permission for BOTH account classes, and the granted scope
        read back from three live runs carries no such permission -- so a call
        to it answers 403, and it used to be the first thing sign-in did after
        acquiring a token. Removing it is what lets sign-in get past its first
        step at all (D-01).

        The identity token arrives with the token response at no extra request
        and no extra permission, and the provider documents it as a superset of
        what its user-info endpoint returns. `sub` is a pairwise,
        per-application subject identifier -- the spike measured two users in
        one tenant returning different values -- which is why it, and not a
        drive id or an address, is what an account's files on disk are keyed by
        (AUTH-21).

        Nothing here is an authorization decision. These claims label a row in a
        list and name a file; the access token is what answers anything that is
        actually a question about permission.
        """
        access_tokens = Utils.default(access_tokens, {})
        claims = device_code.read_identity_claims(
            Utils.get_safe_value(access_tokens, 'id_token', ''))

        key = Utils.str(Utils.get_safe_value(claims, 'sub', ''))
        if not key:
            # Without a subject claim there is no key, and without a key there
            # is nowhere to put this account's credentials. Failing here is
            # correct; inventing a key would put two accounts in one file.
            raise Exception('NoAccountInfo')

        name = Utils.str(Utils.get_safe_value(claims, 'name', ''))
        if not name:
            # The fallback, and the reason it is this one: the default drive
            # answers 200 under this exact scope set on both account classes,
            # and the drive is being fetched a moment later anyway. Whether
            # owner.user.displayName is non-null on a business drive was not
            # transcribed from the spike output; plan 03-13 confirms it live.
            name = self._drive_owner_name(request_params, access_tokens)

        return {'id': key, 'name': name}

    def _drive_owner_name(self, request_params, access_tokens):
        """The drive owner's display name, or '' if the drive will not say.

        Tolerant on purpose. A sign-in that has already succeeded must not be
        undone because a label could not be read; an account with an empty name
        is a cosmetic problem, and an account that failed to be created is not.
        """
        try:
            # The literal is written out here, and again below, rather than
            # held in a constant. A path behind a name is a path
            # test_no_unanswerable_provider_endpoint cannot read, and that
            # sweep is the only thing standing between this file and a 403 that
            # breaks sign-in outright.
            drive = self.get('/me/drive', request_params=request_params,
                             access_tokens=access_tokens)
        except Exception:
            return ''
        owner = Utils.get_safe_value(Utils.default(drive, {}), 'owner', {})
        user = Utils.get_safe_value(Utils.default(owner, {}), 'user', {})
        return Utils.str(Utils.get_safe_value(Utils.default(user, {}),
                                              'displayName', ''))

    def get_drives(self, request_params=None, access_tokens=None):
        """The account's drive. One request, to the default-drive endpoint.

        The two calls this replaces were one wasted round trip and one
        guaranteed failure, and both are measurements rather than opinions
        (SPIKE-DEVICE-CODE.md, against live accounts, with this scope set):

          GET /drives     403 on a work/school account AND on a personal one
          GET /me/drives  403 on a personal account
          GET /me/drive   200 on both

        The old code called /drives, swallowed its 403 and then called
        /me/drives, which meant a personal account got two forbidden responses
        and no drive. This codebase's last piece of apparently-dead code turned
        out to be load-bearing and merely unexplained, so the evidence for this
        deletion is written down rather than assumed (D-04, BROWSE-08).
        """
        drive = self.get('/me/drive', request_params=request_params,
                         access_tokens=access_tokens)
        if not drive or not Utils.get_safe_value(drive, 'id', ''):
            raise Exception('NoDriveInfo')
        return [{
            'id': drive['id'],
            'name': Utils.get_safe_value(drive, 'name', ''),
            'type': Utils.get_safe_value(drive, 'driveType', '')
        }]


    def get_drive_type_name(self, drive_type):
        if drive_type == 'personal':
            return 'OneDrive Personal'
        elif drive_type == 'business':
            return 'OneDrive for Business'
        elif drive_type == 'documentLibrary':
            return ' SharePoint Document Library'
        return drive_type
    
    def get_folder_items(self, item_driveid=None, item_id=None, path=None, on_items_page_completed=None, include_download_info=False, on_before_add_item=None):
        item_driveid = Utils.default(item_driveid, self._driveid)
        if item_id:
            files = self.get('/drives/'+item_driveid+'/items/' + item_id + '/children', parameters = graph_params.listing_parameters())
        elif path == 'sharedWithMe' or path == 'recent':
            files = self.get('/drives/'+self._driveid+'/' + path)
        else:
            if path == '/':
                path = 'root'
            else:
                parts = path.split('/')
                if len(parts) > 1 and not parts[0]:
                    # The user's own path is the only part of this URL that is
                    # not ours, and it is percent-encoded one segment at a time
                    # on the way in. Concatenating it raw is what stopped a
                    # folder whose name contains a space from producing any
                    # request at all: http.client refuses the request line
                    # before the socket is opened (BROWSE-05).
                    #
                    # 'root', 'sharedWithMe' and 'recent' stay untouched. They
                    # are endpoint names this file chose, not user data, and
                    # encoding them would address a folder literally called
                    # "root".
                    path = 'root:'+graph_paths.encode_path(path)+':'
            files = self.get('/drives/'+self._driveid+'/' + path + '/children', parameters = graph_params.listing_parameters())
        if self.cancel_operation():
            # An empty list, never None: a caller that iterates the result would
            # raise TypeError on None, and a cancelled listing is an empty
            # listing rather than a failed one (BROWSE-03).
            return []
        return self.process_files(files, on_items_page_completed, include_download_info, on_before_add_item=on_before_add_item)
    
    def process_files(self, files, on_items_page_completed=None, include_download_info=False, extra_info=None, on_before_add_item=None):
        # The loop, the cancellation contract and the defensive envelope read all
        # live in resources/lib/graph/pager.py. It called itself once per page
        # here, which was measured to raise RecursionError after 998 pages, and
        # its cancel path returned None into an items.extend(None) one frame up.
        #
        # The entry reaches the extractor intact. A shared entry used to be
        # replaced wholesale by its remote half before extraction, which was
        # right about addressing and wrong about labelling; the merge is now
        # field by field inside graph.items.
        return graph_pager.collect_pages(
            files,
            fetch=self.get,
            extract=lambda entry: self._extract_item(entry, include_download_info),
            cancelled=self.cancel_operation,
            on_page=on_items_page_completed,
            on_before_add_item=on_before_add_item,
            extra_info=extra_info,
        )
    
    def _extract_item(self, f, include_download_info=False):
        # The mapping itself lives in resources/lib/graph/items.py, which imports
        # no Kodi module and is therefore testable against recorded JSON without
        # a stub library. The method stays because the vendored callers reach it
        # by name.
        return graph_items.extract_item(f, include_download_info)
    
    def search(self, query, item_driveid=None, item_id=None, on_items_page_completed=None):
        item_driveid = Utils.default(item_driveid, self._driveid)
        url = '/drives/'
        if item_id:
            url += item_driveid+'/items/' + item_id
        else:
            url += self._driveid
        # The user's query is a string literal to the service, so the quote
        # rule applies before the URL rule. Going straight to the percent
        # encoder emitted a single %27, which the service decoded back into a
        # quote that closed the literal -- everything typed after it was then
        # read as expression rather than as text (T-02-02).
        url += '/search(q=\''+graph_paths.odata_quoted(Utils.str(query))+'\')'
        files = self.get(url, parameters = graph_params.search_parameters())
        if self.cancel_operation():
            # BROWSE-03's third site, for the same reason as get_folder_items.
            return []
        return self.process_files(files, on_items_page_completed)
    
    def get_subtitles(self, parent, name, item_driveid=None, include_download_info=False):
        item_driveid = Utils.default(item_driveid, self._driveid)
        subtitles = []
        # Reached through the same rule as `search` above. This call site
        # already doubled by hand; what changes is that the rule now lives in
        # one place instead of two, so the next fix to it cannot land on only
        # one of them.
        search_url = '/drives/'+item_driveid+'/items/' + parent + '/search(q=\''+graph_paths.odata_quoted(Utils.str(Utils.remove_extension(name)))+'\')'
        files = self.get(search_url)
        # Through the same defensive read as every other listing. This is the one
        # call site where an error body is not hypothetical: it is the search
        # endpoint, and the recorded 501 notSupported in the fixture set came
        # back from exactly this endpoint carrying an `error` key and no entry
        # list. Reading the key unconditionally turned a subtitle lookup that
        # found nothing into a KeyError traceback during playback (BROWSE-07).
        for f in graph_pager.entries_of(files):
            subtitle = self._extract_item(f, include_download_info)
            if subtitle['name_extension'].lower() in ('srt','idx','sub','sbv','ass','ssa','smi'):
                subtitles.append(subtitle)
        return subtitles
                
    def get_item(self, item_driveid=None, item_id=None, path=None, find_subtitles=False, include_download_info=False):
        item_driveid = Utils.default(item_driveid, self._driveid)
        if item_id:
            f = self.get('/drives/'+item_driveid+'/items/' + item_id, parameters = graph_params.listing_parameters())
        elif path == 'sharedWithMe' or path == 'recent':
            return
        else:
            if path == '/':
                path = 'root'
            else:
                parts = path.split('/')
                if len(parts) > 1 and not parts[0]:
                    path = 'root:'+path+':'
            f = self.get('/drives/'+self._driveid+'/' + path, parameters = graph_params.listing_parameters())
        
        item = self._extract_item(f, include_download_info)
        if find_subtitles:
            subtitles = self.get_subtitles(item['parent'], item['name'], item_driveid, include_download_info)
            if subtitles:
                item['subtitles'] = subtitles
        return item
    
    def changes(self):
        f = self.get(Utils.default(self.get_change_token(), '/drives/'+self._driveid+'/root/delta?token=latest'), request_params = {'on_exception': self.on_exception})
        extra_info = {}
        changes = self.process_files(f, include_download_info=True, extra_info=extra_info)
        self.persist_change_token(Utils.get_safe_value(extra_info, 'change_token'))
        return changes
    
    def on_exception(self, request, e):
        ex = ExceptionUtils.extract_exception(e, HTTPError)
        if ex and ex.code == 404:
            self.persist_change_token(None)