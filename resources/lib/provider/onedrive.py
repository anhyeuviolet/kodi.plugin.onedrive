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
from resources.lib.graph import paths as graph_paths
from resources.lib.vendor.clouddrive_common.remote.provider import Provider
from resources.lib.vendor.clouddrive_common.utils import Utils
from resources.lib.vendor.clouddrive_common.exception import ExceptionUtils

import urllib.parse
from urllib.error import HTTPError

class OneDrive(Provider):
    _extra_parameters = {'expand': 'thumbnails'}
    
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
            files = self.get('/drives/'+item_driveid+'/items/' + item_id + '/children', parameters = self._extra_parameters)
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
            files = self.get('/drives/'+self._driveid+'/' + path + '/children', parameters = self._extra_parameters)
        if self.cancel_operation():
            return
        return self.process_files(files, on_items_page_completed, include_download_info, on_before_add_item=on_before_add_item)
    
    def process_files(self, files, on_items_page_completed=None, include_download_info=False, extra_info=None, on_before_add_item=None):
        items = []
        for f in files['value']:
            f = Utils.get_safe_value(f, 'remoteItem', f)
            item = self._extract_item(f, include_download_info)
            if on_before_add_item:
                on_before_add_item(item)
            items.append(item)
        if on_items_page_completed:
            on_items_page_completed(items)
        if type(extra_info) is dict:
            if '@odata.deltaLink' in files:
                extra_info['change_token'] = files['@odata.deltaLink']
                
        if '@odata.nextLink' in files:
            next_files = self.get(files['@odata.nextLink'])
            if self.cancel_operation():
                return
            items.extend(self.process_files(next_files, on_items_page_completed, include_download_info, extra_info, on_before_add_item))
        return items
    
    def _extract_item(self, f, include_download_info=False):
        name = Utils.get_safe_value(f, 'name', '')
        parent_reference = Utils.get_safe_value(f, 'parentReference', {})
        item = {
            'id': f['id'],
            'name': name,
            'name_extension' : Utils.get_extension(name),
            'drive_id' : Utils.get_safe_value(parent_reference, 'driveId'),
            'parent' : Utils.get_safe_value(parent_reference, 'id'),
            'mimetype' : Utils.get_safe_value(Utils.get_safe_value(f, 'file', {}), 'mimeType'),
            'last_modified_date' : Utils.get_safe_value(f,'lastModifiedDateTime'),
            'size': Utils.get_safe_value(f, 'size', 0),
            'description': Utils.get_safe_value(f, 'description', ''),
            'deleted': 'deleted' in f
        }
        if 'folder' in f:
            item['folder'] = {
                'child_count' : Utils.get_safe_value(f['folder'],'childCount',0)
            }
        if 'video' in f:
            video = f['video']
            item['video'] = {
                'width' : Utils.get_safe_value(video,'width', 0),
                'height' : Utils.get_safe_value(video, 'height', 0),
                'duration' : Utils.get_safe_value(video, 'duration', 0) /1000
            }
        if 'audio' in f:
            audio = f['audio']
            item['audio'] = {
                'tracknumber' : Utils.get_safe_value(audio, 'track'),
                'discnumber' : Utils.get_safe_value(audio, 'disc'),
                'duration' : int(Utils.get_safe_value(audio, 'duration') or '0') / 1000,
                'year' : Utils.get_safe_value(audio, 'year'),
                'genre' : Utils.get_safe_value(audio, 'genre'),
                'album': Utils.get_safe_value(audio, 'album'),
                'artist': Utils.get_safe_value(audio, 'artist'),
                'title': Utils.get_safe_value(audio, 'title')
            }
        if 'image' in f or 'photo' in f:
            item['image'] = {
                'size' : Utils.get_safe_value(f, 'size', 0)
            }
        if 'thumbnails' in f and type(f['thumbnails']) == list and len(f['thumbnails']) > 0:
            thumbnails = f['thumbnails'][0]
            item['thumbnail'] = Utils.get_safe_value(Utils.get_safe_value(thumbnails, 'large', {}), 'url', '')
        if include_download_info:
            item['download_info'] =  {
                'url' : Utils.get_safe_value(f,'@microsoft.graph.downloadUrl')
            }
        return item
    
    def search(self, query, item_driveid=None, item_id=None, on_items_page_completed=None):
        item_driveid = Utils.default(item_driveid, self._driveid)
        url = '/drives/'
        if item_id:
            url += item_driveid+'/items/' + item_id
        else:
            url += self._driveid
        url += '/search(q=\''+urllib.parse.quote(Utils.str(query))+'\')'
        self._extra_parameters['filter'] = 'file ne null'
        files = self.get(url, parameters = self._extra_parameters)
        if self.cancel_operation():
            return
        return self.process_files(files, on_items_page_completed)
    
    def get_subtitles(self, parent, name, item_driveid=None, include_download_info=False):
        item_driveid = Utils.default(item_driveid, self._driveid)
        subtitles = []
        search_url = '/drives/'+item_driveid+'/items/' + parent + '/search(q=\''+urllib.parse.quote(Utils.str(Utils.remove_extension(name)).replace("'","''"))+'\')'
        files = self.get(search_url)
        for f in files['value']:
            subtitle = self._extract_item(f, include_download_info)
            if subtitle['name_extension'].lower() in ('srt','idx','sub','sbv','ass','ssa','smi'):
                subtitles.append(subtitle)
        return subtitles
                
    def get_item(self, item_driveid=None, item_id=None, path=None, find_subtitles=False, include_download_info=False):
        item_driveid = Utils.default(item_driveid, self._driveid)
        if item_id:
            f = self.get('/drives/'+item_driveid+'/items/' + item_id, parameters = self._extra_parameters)
        elif path == 'sharedWithMe' or path == 'recent':
            return
        else:
            if path == '/':
                path = 'root'
            else:
                parts = path.split('/')
                if len(parts) > 1 and not parts[0]:
                    path = 'root:'+path+':'
            f = self.get('/drives/'+self._driveid+'/' + path, parameters = self._extra_parameters)
        
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