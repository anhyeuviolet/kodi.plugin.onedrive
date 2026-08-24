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

import inspect
import json
import os
import sys
import threading
import time
import urllib.parse
from urllib.error import HTTPError, URLError

from resources.lib.auth import device_code, errors, store
from resources.lib.kodi import auth_context
from resources.lib.vendor.clouddrive_common.account import AccountManager, AccountNotFoundException, \
    DriveNotFoundException
from resources.lib.vendor.clouddrive_common.exception import UIException, ExceptionUtils, RequestException
from resources.lib.vendor.clouddrive_common.export import ExportManager
from resources.lib.vendor.clouddrive_common.remote.provider import ReauthorisationRequired
from resources.lib.vendor.clouddrive_common.remote.request import Request
from resources.lib.vendor.clouddrive_common.service.download import DownloadServiceUtil
from resources.lib.vendor.clouddrive_common.ui.dialog import DialogProgress, DialogProgressBG, \
    QRDialogProgress, ExportMainDialog
from resources.lib.vendor.clouddrive_common.ui.logger import Logger
from resources.lib.vendor.clouddrive_common.ui.utils import KodiUtils
from resources.lib.vendor.clouddrive_common.utils import Utils
import xbmcgui
import xbmcplugin
import xbmcvfs
from datetime import timedelta, datetime
from resources.lib.vendor.clouddrive_common.cache.cache import Cache


class CloudDriveAddon:
    _addon = None
    _addon_handle = None
    _addonid = None
    _addon_name = None
    _addon_params = None
    _addon_url = None
    _addon_version = None
    _common_addon = None
    _cancel_operation = False
    _content_type = None
    _dialog = None
    _export_manager = None
    _child_count_supported = True
    _auto_refreshed_slideshow_supported = True
    _load_target = 0
    _load_count = 0
    _profile_path = None
    _progress_dialog = None
    _progress_dialog_bg = None
    _system_monitor = None
    _video_file_extensions = [x for x in KodiUtils.get_supported_media("video") if x not in ('','zip')]
    _audio_file_extensions = KodiUtils.get_supported_media("music")
    _image_file_extensions = KodiUtils.get_supported_media("picture")
    _account_manager = None
    _action = None

    def __init__(self):
        self._addon = KodiUtils.get_addon()
        self._addonid = self._addon.getAddonInfo('id')
        self._addon_name = self._addon.getAddonInfo('name')
        self._addon_url = sys.argv[0]
        self._addon_version = self._addon.getAddonInfo('version')
        self._common_addon_id = KodiUtils.common_addon_id
        self._common_addon = KodiUtils.get_addon(self._common_addon_id)
        self._common_addon_version = self._common_addon.getAddonInfo('version')
        self._dialog = xbmcgui.Dialog()
        self._profile_path = Utils.unicode(KodiUtils.translate_path(self._addon.getAddonInfo('profile')))
        self._progress_dialog = DialogProgress(self._addon_name)
        self._progress_dialog_bg = DialogProgressBG(self._addon_name)
        self._system_monitor = KodiUtils.get_system_monitor()
        self._account_manager = AccountManager(self._profile_path)
        self._pin_dialog = None
        self.iskrypton = KodiUtils.get_home_property('iskrypton') == 'true'
        
        if len(sys.argv) > 1:
            self._addon_handle = int(sys.argv[1])
            self._addon_params = urllib.parse.parse_qs(sys.argv[2][1:])
            for param in self._addon_params:
                self._addon_params[param] = self._addon_params.get(param)[0]
            self._content_type = Utils.get_safe_value(self._addon_params, 'content_type')
            if not self._content_type:
                wid = xbmcgui.getCurrentWindowId()
                if wid == 10005 or wid == 10500 or wid == 10501 or wid == 10502:
                    self._content_type = 'audio'
                elif wid == 10002:
                    self._content_type = 'image'
                else:
                    self._content_type = 'video'
            xbmcplugin.addSortMethod(handle=self._addon_handle, sortMethod=xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.addSortMethod(handle=self._addon_handle, sortMethod=xbmcplugin.SORT_METHOD_UNSORTED ) 
            xbmcplugin.addSortMethod(handle=self._addon_handle, sortMethod=xbmcplugin.SORT_METHOD_SIZE )
            xbmcplugin.addSortMethod(handle=self._addon_handle, sortMethod=xbmcplugin.SORT_METHOD_DATE )
            xbmcplugin.addSortMethod(handle=self._addon_handle, sortMethod=xbmcplugin.SORT_METHOD_DURATION )
    
    def __del__(self):
        del self._addon
        del self._common_addon
        del self._dialog
        del self._progress_dialog
        del self._progress_dialog_bg
        del self._system_monitor
        del self._account_manager
        
    def get_provider(self):
        raise NotImplementedError()
    
    def get_my_files_menu_name(self):
        return self._common_addon.getLocalizedString(32052)
    
    def get_custom_drive_folders(self, driveid):
        return
    
    def cancel_operation(self):
        return self._system_monitor.abortRequested() or self._progress_dialog.iscanceled() or self._cancel_operation or (self._pin_dialog and self._pin_dialog.iscanceled())

    def _get_display_name(self, account, drive=None, with_format=False):
        return self._account_manager.get_account_display_name(account, drive, self.get_provider(), with_format)
    
    def get_accounts(self, with_format=False):
        accounts = self._account_manager.get_accounts()
        for account_id in accounts:
            account = accounts[account_id]
            for drive in account['drives']:
                drive['display_name'] = self._get_display_name(account, drive, with_format)
        return accounts
                    
    # The key the background service writes onto an account record when a
    # refresh comes back as a provider grant failure. The service never prompts
    # -- it runs at Kodi start with nobody in front of the television -- so this
    # list is the entire channel by which that failure reaches a person
    # (AUTH-17). It lives on the record and not in the token file, because an
    # unreadable token file is one of the failures being signalled.
    #
    # Plan 03-10 is the writer; this is the reader. The two are coupled by this
    # name and by nothing else.
    NEEDS_REAUTH_KEY = 'needs_reauth'

    def _needs_reauthorisation(self, account):
        return bool(Utils.get_safe_value(account, self.NEEDS_REAUTH_KEY, False))

    def list_accounts(self):
        accounts = self.get_accounts(with_format=True)
        listing = []
        for account_id in accounts:
            account = accounts[account_id]
            stale = self._needs_reauthorisation(account)
            # One row per account. Drive resolution is a single call to
            # /me/drive, which answers with the default drive and only that, so
            # this loop runs exactly once per account -- and the branch that
            # used to offer per-drive removal when it ran more than once has
            # gone with the endpoints that could have produced a second drive.
            for drive in account['drives']:
                context_options = []
                params = {'action':'_search', 'content_type': self._content_type, 'driveid': drive['id']}
                cmd = 'ActivateWindow(%d,%s?%s)' % (xbmcgui.getCurrentWindowId(), self._addon_url, urllib.parse.urlencode(params))
                context_options.append((self._common_addon.getLocalizedString(32039), cmd))
                params['action'] = '_reauthorise_account'
                reauthorise_cmd = 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'
                context_options.append((self._addon_string(30042), reauthorise_cmd))
                params['action'] = '_remove_account'
                context_options.append((self._common_addon.getLocalizedString(32006), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'))
                label = drive['display_name']
                if stale:
                    # Marked in the label rather than only in a context menu
                    # nobody opens. The colour is a hex value, not a name: a
                    # name resolves through the skin's colour theme and an
                    # unresolved one fails silently, which is the whole shape
                    # of Pitfall 5.
                    label = '%s [COLOR FFFF6666][%s][/COLOR]' % (
                        label, self._addon_string(30043))
                list_item = xbmcgui.ListItem(label)
                list_item.addContextMenuItems(context_options)
                if stale:
                    # Default action is signing in again, not browsing. Browsing
                    # would make its first request with the credential that
                    # already failed and show the user a network error instead
                    # of the one thing that fixes it. Not a folder, for the same
                    # reason _add_account's row is not: it releases the handle
                    # and re-enters as an action.
                    params['action'] = '_reauthorise_account'
                    url = self._addon_url + '?' + urllib.parse.urlencode(params)
                    listing.append((url, list_item))
                    continue
                params = {'action':'_list_drive', 'content_type': self._content_type, 'driveid': drive['id']}
                url = self._addon_url + '?' + urllib.parse.urlencode(params)
                listing.append((url, list_item, True))
        # The row still carries a plugin address rather than a RunPlugin
        # command, because a directory item's path is not a builtin. What
        # changed is what happens on the other side: _add_account releases the
        # handle immediately and re-enters as an action, so Kodi is not left
        # holding a container fetch for the life of a device code.
        list_item = xbmcgui.ListItem(self._common_addon.getLocalizedString(32005))
        params = {'action':'_add_account', 'content_type': self._content_type}
        url = self._addon_url + '?' + urllib.parse.urlencode(params)
        listing.append((url, list_item))
        xbmcplugin.addDirectoryItems(self._addon_handle, listing, len(listing))
        xbmcplugin.endOfDirectory(self._addon_handle, True)
    
    def _addon_string(self, string_id):
        """A string from THIS add-on's own catalogue.

        Deliberately not KodiUtils.localize. That helper sends every id below
        32000 to xbmc.getLocalizedString, which reads Kodi's own catalogue --
        correct before this add-on was renumbered into the 30000 block Kodi
        reserves for plugins, and silently the wrong sentence ever since. The
        vendored module's own 32000-32088 still go through _common_addon, which
        is what keeps the two blocks readable apart.
        """
        return self._addon.getLocalizedString(string_id)

    # -- signing in --------------------------------------------------------
    #
    # What one pass of the poll loop can end as. Four and only four, so a
    # caller cannot quietly forget one.
    _SIGNIN_AUTHORISED = 'authorised'
    _SIGNIN_ABANDONED = 'abandoned'
    _SIGNIN_NEW_CODE = 'new_code'
    _SIGNIN_REFUSED = 'refused'

    def _released_the_handle(self, params):
        """True if this invocation handed the directory handle back.

        Kodi holds a directory handle for the whole of a plugin invocation. A
        sign-in runs for as long as the server says the code lives -- three
        spike runs differed by nearly fifteen minutes -- and a container fetch
        blocked for a quarter of an hour is not a listing that is slow, it is an
        add-on that is broken.

        So the handle is released and the work re-enters as an action.
        RunPlugin invokes a plugin with sys.argv[1] == '-1', so the second
        invocation arrives with a negative handle, gets False from here and does
        the work. The context-menu entries in list_accounts already use exactly
        this mechanism, so it is this file's own idiom rather than an import,
        and resources/lib/addon.py already guards on a negative handle.

        Observed rather than settled. It follows from documented behaviour and
        from this tree's own patterns, but it has not been run; plan 03-14 runs
        it on the television.
        """
        if self._addon_handle is None or self._addon_handle < 0:
            return False
        xbmcplugin.endOfDirectory(self._addon_handle, succeeded=False,
                                  updateListing=False, cacheToDisc=False)
        KodiUtils.executebuiltin('RunPlugin(%s?%s)' % (
            self._addon_url, urllib.parse.urlencode(params)))
        return True

    def _signin_request_params(self):
        return {
            'waiting_retry': lambda request, remaining: self._progress_dialog_bg.update(
                int((request.current_delay - remaining)/request.current_delay*100),
                heading=self._common_addon.getLocalizedString(32043) % ('' if request.current_tries == 1 else ' again'),
                message=self._common_addon.getLocalizedString(32044) % str(int(remaining)) + ' ' +
                        self._common_addon.getLocalizedString(32045) % (str(request.current_tries + 1), str(request.tries))
            ),
            'on_complete': lambda request: (self._progress_dialog.close(), self._progress_dialog_bg.close()),
            'cancel_operation': self.cancel_operation,
            'wait': self._system_monitor.waitForAbort
        }

    def _acquire_tokens(self, provider, request_params):
        """The device-code exchange, from first code to authorised payload.

        Returns the token response, or None if the user cancelled, Kodi is
        shutting down, or the provider refused. Shared by adding an account and
        by re-authorising one, because it is the same exchange either way -- the
        only thing that differs is what is done with what comes back.
        """
        self._progress_dialog.update(0, self._common_addon.getLocalizedString(32008))

        response = provider.request_device_code(request_params)
        self._progress_dialog.close()
        if self.cancel_operation():
            return None
        if not response or not Utils.get_safe_value(response, 'device_code', ''):
            raise Exception('Unable to retrieve a device code')

        request_params['on_complete'] = lambda request: self._progress_dialog_bg.close()
        # Two sentences: what to do, and the one that stops a personal account
        # abandoning halfway. Those users are asked to sign in a second time on
        # the phone and read it as the add-on having failed.
        line1 = self._addon_string(30037) + '[CR]' + self._addon_string(30041)
        # The address the server returned, passed through untouched and never
        # composed. It is login.microsoft.com/device, which is not the address
        # most documentation cites, and the field that would let the code
        # travel inside it is absent from the response -- so the code goes in
        # its own control and the image carries the address alone (AUTH-08).
        line2 = '[B]%s[/B]' % Utils.str(response['verification_uri'])
        self._pin_dialog = QRDialogProgress.create(
            self._addon_name, response['verification_uri'], line1, line2, '',
            code=response['user_code'])
        self._pin_dialog.show()

        tokens_info = None
        while True:
            outcome, payload = self._await_authorisation(provider, response,
                                                         request_params)
            if outcome == self._SIGNIN_AUTHORISED:
                # Stamped the moment it arrives, and never later. The provider
                # sends `expires_in` and no `date`; `date` is stamped locally
                # and it is one of the four fields
                # OAuth2._validate_access_tokens requires, as well as the one
                # OAuth2.prepare_request computes expiry from. So the raw poll
                # response is rejected by the FIRST request made with it, and a
                # sign-in that actually succeeded is reported to the user as a
                # failure -- which is what it did on hardware.
                #
                # Through store.merge_token_response, which is the single
                # implementation of the merge rule in the tree, against an
                # empty previous blob because nothing is stored for this
                # account yet. It is a pure function and writes nothing, so
                # everything below still happens in memory: the "nothing is
                # written until the last two statements" property of
                # _add_account and _reauthorise_account is untouched (AUTH-07).
                #
                # Here rather than in _await_authorisation, whose payload is a
                # refusal code for one of its four outcomes and which is
                # protocol-level throughout; and rather than in
                # provider.poll_for_token, which would have to re-derive which
                # of its states are successes. This is the one point where a
                # poll payload becomes the token blob the rest of the flow
                # uses, so it is where the local half of the blob belongs.
                tokens_info = store.merge_token_response({}, payload)
                break
            if outcome != self._SIGNIN_NEW_CODE:
                self._pin_dialog.close()
                if outcome == self._SIGNIN_REFUSED:
                    # Shown rather than raised. A refusal by the identity
                    # provider is an answer, not a fault, and raising would put
                    # it through the failure handler.
                    self._dialog.ok(self._addon_name,
                                    self._addon_string(30044) % Utils.str(payload))
                return None
            # A fresh code, with its own expiry and its own interval. Reusing
            # the previous response's would put a countdown on screen that the
            # server never agreed to.
            response = provider.request_device_code(request_params)
            if not response or not Utils.get_safe_value(response, 'device_code', ''):
                self._pin_dialog.close()
                raise Exception('Unable to retrieve a device code')
            self._pin_dialog.reset_for_new_code(line1, line2, '')
            self._pin_dialog.set_code(response['user_code'])
        self._pin_dialog.close()

        if self.cancel_operation():
            return None
        return tokens_info

    def _identify(self, provider, request_params, tokens_info):
        """The account the token that just arrived belongs to.

        Label from the `name` claim, key from the `sub` claim -- both carried by
        the identity token itself, at no extra request and no extra permission.
        """
        self._progress_dialog.update(25, self._common_addon.getLocalizedString(32064),' ',' ')
        try:
            return provider.get_account(request_params = request_params, access_tokens = tokens_info)
        except Exception as e:
            raise UIException(32065, e)

    def _add_account(self):
        if self._released_the_handle({'action': '_add_account',
                                      'content_type': self._content_type}):
            return

        request_params = self._signin_request_params()
        provider = self.get_provider()
        tokens_info = self._acquire_tokens(provider, request_params)
        if self.cancel_operation() or not tokens_info:
            return

        # Everything below is assembled in memory. Nothing is written until the
        # last two statements, so a cancel anywhere above returns having written
        # nothing and there is no partial account to leave behind. That is a
        # structural property rather than a chain of guards each of which has to
        # be right (AUTH-07).
        account = self._identify(provider, request_params, tokens_info)
        if self.cancel_operation():
            return

        self._progress_dialog.update(50, self._common_addon.getLocalizedString(32017))
        try:
            account['drives'] = provider.get_drives(request_params = request_params, access_tokens = tokens_info)
        except Exception as e:
            raise UIException(32018, e)
        if self.cancel_operation():
            return

        self._progress_dialog.update(75, self._common_addon.getLocalizedString(32020))
        try:
            # The credential goes to this account's own file at mode 0600, not
            # inside the account record. A token in the record is a token in
            # whatever the record is stored in and copied wherever the record is
            # copied (AUTH-11).
            provider.save_tokens(account['id'], tokens_info)
            self._account_manager.save_account(account)
        except Exception as e:
            raise UIException(32021, e)

        self._progress_dialog.close()
        KodiUtils.executebuiltin('Container.Refresh')

    def _reauthorise_account(self, driveid):
        """Sign in again for an account that already exists.

        This is the far end of the background service's silent failure. The
        service refreshes at Kodi start with nobody in front of the television,
        so it may not prompt; when a refresh comes back as a provider grant
        failure it writes NEEDS_REAUTH_KEY onto the record and stops. The list
        renders that record distinctly and points it here, and the user chooses
        to sign in (AUTH-17). It is also how a tenant-block message reaches
        somebody who was signed in and then got blocked.
        """
        if self._released_the_handle({'action': '_reauthorise_account',
                                      'content_type': self._content_type,
                                      'driveid': driveid}):
            return

        existing = self._account_manager.get_by_driveid('account', driveid)
        request_params = self._signin_request_params()
        provider = self.get_provider()
        tokens_info = self._acquire_tokens(provider, request_params)
        if self.cancel_operation() or not tokens_info:
            return

        signed_in = self._identify(provider, request_params, tokens_info)
        if self.cancel_operation():
            return

        if Utils.str(signed_in['id']) != Utils.str(existing['id']):
            # A different account signed in on the phone. Writing this blob
            # against the record that was chosen would bind one person's
            # credential to another person's row, and every request afterwards
            # would read the wrong drive under the right label -- silently, and
            # on a device more than one person uses. So nothing is written and
            # the user is told which account actually signed in.
            self._progress_dialog.close()
            Logger.notice('re-authorisation abandoned: a different account '
                          'signed in')
            self._dialog.ok(self._addon_name, self._addon_string(30059)
                            % Utils.unicode(signed_in['name']))
            return

        # Assembled in memory, written last, exactly as adding an account is.
        # The stored drives are kept rather than fetched again: the drive id is
        # what every list row and every stored export references, and refetching
        # it to arrive at the same value only adds a request that can fail.
        account = dict(existing)
        account['name'] = signed_in['name']
        account.pop(self.NEEDS_REAUTH_KEY, None)

        self._progress_dialog.update(75, self._common_addon.getLocalizedString(32020))
        try:
            provider.save_tokens(account['id'], tokens_info)
            self._account_manager.save_account(account)
        except Exception as e:
            raise UIException(32021, e)

        self._progress_dialog.close()
        KodiUtils.executebuiltin('Container.Refresh')

    def _await_authorisation(self, provider, response, request_params):
        """Drive the dialog and the poll until one of the four outcomes.

        Two clocks and one sleep.

        The sleep is the abort-aware wait, one second, and it is simultaneously
        the countdown's tick and the shutdown check -- so Kodi shutting down is
        noticed within a second no matter where the poll interval stands. Never
        time.sleep and never xbmc.sleep: neither observes the abort flag, and a
        loop that can run for a quarter of an hour must not be the reason a
        shutdown hangs.

        The two deadlines are the code's expiry and the next poll time, and
        neither is derived from the other. The loop this replaces disambiguated
        them with a modulus on the remaining seconds, which couples the
        countdown's refresh rate to the poll interval and breaks the moment a
        slow_down answer raises that interval.
        """
        code = response['device_code']
        interval = Utils.get_safe_value(response, 'interval', 0)
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = 0
        if interval <= 0:
            # RFC 8628 section 3.4: five seconds if the server did not say.
            interval = device_code.DEFAULT_INTERVAL

        expires_in = Utils.get_safe_value(response, 'expires_in', 0)
        try:
            expires_in = int(expires_in)
        except (TypeError, ValueError):
            expires_in = 0
        # The server's own value for THIS code and nothing else. The provider
        # randomises it -- three observed runs differed by nearly fifteen
        # minutes -- so the two-minute constant this replaces was wrong by
        # measurement, and no constant takes its place (AUTH-06).
        deadline = time.time() + max(expires_in, device_code.DEFAULT_INTERVAL)
        next_poll = time.time()
        expired = False

        while True:
            if self.cancel_operation():
                return self._SIGNIN_ABANDONED, None
            if self._pin_dialog.is_new_code_requested():
                return self._SIGNIN_NEW_CODE, None

            now = time.time()
            if not expired and now >= deadline:
                # Stop polling: the code is dead and the endpoint would only
                # say so. The dialog moves to its expiry state, which is also
                # what puts focus on the second action, so it arrives ready to
                # press on a remote with no pointer.
                expired = True
                self._pin_dialog.set_expired()

            if not expired:
                self._pin_dialog.set_remaining(int(deadline - now))
                if now >= next_poll:
                    state, payload = self._poll_once(provider, code,
                                                     request_params)
                    if state == device_code.OK:
                        return self._SIGNIN_AUTHORISED, payload
                    if state == device_code.TERMINAL:
                        failure = errors.classify_response(payload)
                        Logger.error('sign-in refused: %s (%s)'
                                     % (failure.outcome,
                                        failure.code or 'no code'))
                        return self._SIGNIN_REFUSED, (failure.code
                                                      or failure.outcome)
                    # RFC 8628 section 3.5: a slow_down raises the interval for
                    # this and every subsequent request. Feeding the result
                    # back in is the whole of the permanence -- recomputing it
                    # from the server's original value would undo the increase
                    # on the next tick and earn another slow_down.
                    interval = device_code.next_interval(interval, state)
                    next_poll = time.time() + interval

            if self._system_monitor.waitForAbort(1):
                return self._SIGNIN_ABANDONED, None

    def _poll_once(self, provider, code, request_params):
        """One poll, with a network failure reported as "keep waiting".

        A body that would not parse carries no error code to classify, and a
        connection that never completed says nothing about the grant. Treating
        either as a refusal would end a sign-in because a hotel Wi-Fi had a
        moment -- and the user is standing in front of a television with the
        code already typed into their phone.
        """
        try:
            return provider.poll_for_token(code, request_params)
        except device_code.TransportError as e:
            Logger.debug('poll: not a protocol answer (%s); still waiting' % e)
        except RequestException as e:
            Logger.debug('poll: transport failed (%s); still waiting' % e)
        except URLError as e:
            Logger.debug('poll: network unreachable (%s); still waiting' % e)
        return device_code.PENDING, None

    # The per-drive removal option and its handler stood here. Drive resolution
    # is a single call to GET /me/drive, which answers with the default drive
    # and only that -- GET /drives is 403 on both account classes and is not a
    # v1.0 endpoint at all, and GET /me/drives is 403 accessDenied for personal
    # accounts. An account therefore carries exactly one drive, the branch that
    # offered this option when it carried more than one can never be taken, and
    # the option was unreachable rather than merely unused. The measurement is
    # in the commit body; the document-library work deferred out of this
    # milestone would need drive selection again, and the shape to restore is
    # OneDrive.get_drives together with this handler.

    def _remove_account(self, driveid):
        account = self._account_manager.get_by_driveid('account', driveid)
        if self._dialog.yesno(self._addon_name, self._common_addon.getLocalizedString(32022) % self._get_display_name(account, with_format=True)):
            self._account_manager.remove_account(account['id'])
            # The record is what the list reads, so removing it alone makes the
            # removal look complete. The token file and the lock file sit beside
            # it under accounts/, and an account removed and then re-added would
            # inherit the stale blob -- producing a refresh refused against a
            # credential the user believes they just replaced, with no visible
            # cause (AUTH-20, T-03-43). Both files go, tolerating either being
            # absent already.
            store.remove_account(auth_context.profile_path(), account['id'])
            KodiUtils.executebuiltin('Container.Refresh')
        
    def _list_drive(self, driveid):
        drive_folders = self.get_custom_drive_folders(driveid)
        if self.cancel_operation():
            return
        if drive_folders:
            listing = []
            url = self._addon_url + '?' + urllib.parse.urlencode({'action':'_list_folder', 'path': '/', 'content_type': self._content_type, 'driveid': driveid})
            listing.append((url, xbmcgui.ListItem('[B]%s[/B]' % self.get_my_files_menu_name()), True))
            for folder in drive_folders:
                params = {'action':'_list_folder', 'path': folder['path'], 'content_type': self._content_type, 'driveid': driveid}
                if 'params' in folder:
                    params.update(folder['params'])
                url = self._addon_url + '?' + urllib.parse.urlencode(params)
                list_item = xbmcgui.ListItem(Utils.unicode(folder['name']))
                if 'context_options' in folder:
                    list_item.addContextMenuItems(folder['context_options'])
                listing.append((url, list_item, True))
            if self._content_type == 'video' or self._content_type == 'audio':
                url = self._addon_url + '?' + urllib.parse.urlencode({'action':'_list_exports', 'content_type': self._content_type, 'driveid': driveid})
                listing.append((url, xbmcgui.ListItem(self._common_addon.getLocalizedString(32000)), True))
            url = self._addon_url + '?' + urllib.parse.urlencode({'action':'_search', 'content_type': self._content_type, 'driveid': driveid})
            listing.append((url, xbmcgui.ListItem(self._common_addon.getLocalizedString(32039)), True))
            
            xbmcplugin.addDirectoryItems(self._addon_handle, listing, len(listing))
            xbmcplugin.endOfDirectory(self._addon_handle, True)
        else:
            self._list_folder(driveid, path='/')

    def _list_exports(self, driveid):
        self._export_manager = ExportManager(self._profile_path)
        exports = self._export_manager.get_exports()
        listing = []
        for exportid in exports:
            export = exports[exportid]
            if export['driveid'] == driveid and export['content_type'] == self._content_type:
                item_name = Utils.unicode(export['name'])
                params = {'action':'_open_export', 'content_type': self._content_type, 'driveid': driveid, 'item_driveid': export['item_driveid'], 'item_id': export['id'], 'name': urllib.parse.quote(Utils.str(item_name))}
                url = self._addon_url + '?' + urllib.parse.urlencode(params)
                list_item = xbmcgui.ListItem(item_name)
                context_options = []
                params['action'] = '_run_export'
                context_options.append((KodiUtils.localize(21479), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'))
                params['action'] = '_remove_export'
                context_options.append((KodiUtils.localize(1210), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'))
                list_item.addContextMenuItems(context_options)
                listing.append((url, list_item, True))
        xbmcplugin.addDirectoryItems(self._addon_handle, listing, len(listing))
        xbmcplugin.endOfDirectory(self._addon_handle, True)
    
    def _run_export(self, driveid, item_id):
        self._export_manager = ExportManager(self._profile_path)
        export = self._export_manager.get_exports()[item_id]
        export['run_immediately'] = True
        self._export_manager.save_export(export)
        KodiUtils.show_notification(self._common_addon.getLocalizedString(32055) % '60')
    
    def _remove_export(self, driveid, item_id):
        self._export_manager = ExportManager(self._profile_path)
        exports = self._export_manager.get_exports()
        if item_id in exports:
            item = exports[item_id]
            remove_export = self._dialog.yesno(self._addon_name, self._common_addon.getLocalizedString(32001) % Utils.unicode(item['name']))
            if remove_export:
                keep_locals = self._dialog.yesno(self._addon_name, self._common_addon.getLocalizedString(32086) % Utils.unicode(item['name']))
                if not keep_locals:
                    self._export_manager.remove_export(item_id, False)
                else:
                    self._export_manager.remove_export(item_id)
                KodiUtils.executebuiltin('Container.Refresh')
        else:
            KodiUtils.executebuiltin('Container.Refresh')
    
    def _open_export(self, driveid, item_driveid, item_id, name):
        export_dialog = ExportMainDialog.create(self._content_type, driveid, item_driveid, item_id, name, self._account_manager, self.get_provider())
        export_dialog.doModal()
        if export_dialog.run:
            KodiUtils.show_notification(self._common_addon.getLocalizedString(32055) % '60')
    
    def on_items_page_completed(self, items):
        self._load_count += len(items)
        if self._load_target > self._load_count:
            percent = int(round(float(self._load_count)/self._load_target*100))
            self._progress_dialog_bg.update(percent, self._addon_name, self._common_addon.getLocalizedString(32047) % (Utils.str(self._load_count), Utils.str(self._load_target)))
        else:
            self._progress_dialog_bg.update(100, self._addon_name, self._common_addon.getLocalizedString(32048) % Utils.str(self._load_count))
            
    def _list_folder(self, driveid, item_driveid=None, item_id=None, path=None):
        self.get_provider().configure(self._account_manager, driveid)
        if self._child_count_supported:
            item = self.get_provider().get_item(item_driveid, item_id, path)
            if item:
                self._load_target = item['folder']['child_count']
                self._progress_dialog_bg.create(self._addon_name, self._common_addon.getLocalizedString(32049) % Utils.str(self._load_target))
        
        items = self.get_provider().get_folder_items(item_driveid, item_id, path, on_items_page_completed = self.on_items_page_completed)
        if self.cancel_operation():
            return
        self._process_items(items, driveid)
        
    def _process_items(self, items, driveid):
        listing = []
        for item in items:
            Logger.debug(item)
            item_id = item['id']
            item_name = Utils.unicode(item['name'])
            item_name_extension = item['name_extension']
            item_driveid = Utils.default(Utils.get_safe_value(item, 'drive_id'), driveid)
            list_item = xbmcgui.ListItem(item_name)
            url = None
            is_folder = 'folder' in item
            params = {'content_type': self._content_type, 'item_driveid': item_driveid, 'item_id': item_id, 'driveid': driveid}
            if 'extra_params' in item:
                params.update(item['extra_params'])
            context_options = []
            info = {'size': item['size'], 'date': KodiUtils.to_kodi_item_date_str(KodiUtils.to_datetime(Utils.get_safe_value(item, 'last_modified_date')))}
            if is_folder:
                params['action'] = '_list_folder'
                url = self._addon_url + '?' + urllib.parse.urlencode(params)
                params['action'] = '_search'
                cmd = 'ActivateWindow(%d,%s?%s)' % (xbmcgui.getCurrentWindowId(), self._addon_url, urllib.parse.urlencode(params))
                context_options.append((self._common_addon.getLocalizedString(32039), cmd))
                if self._content_type == 'audio' or self._content_type == 'video':
                    params['action'] = '_open_export'
                    params['name'] = urllib.parse.quote(Utils.str(item_name))
                    context_options.append((self._common_addon.getLocalizedString(32004), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'))
                    del params['name']
                elif self._content_type == 'image' and self._auto_refreshed_slideshow_supported:
                    params['action'] = '_slideshow'
                    context_options.append((self._common_addon.getLocalizedString(32032), 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'))
            elif (('video' in item or (item_name_extension and item_name_extension in self._video_file_extensions)) and self._content_type == 'video') or (('audio' in item or (item_name_extension and item_name_extension in self._audio_file_extensions)) and self._content_type == 'audio'):
                list_item.setProperty('IsPlayable', 'true')
                params['action'] = 'download'
                cmd = 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'
                context_options.append((self._common_addon.getLocalizedString(32051), cmd))
                params['action'] = 'play'
                url = self._addon_url + '?' + urllib.parse.urlencode(params)
                info_type = self._content_type
                if 'audio' in item:
                    info.update(item['audio'])
                    info_type = 'music'
                elif 'video' in item:
                    list_item.addStreamInfo('video', item['video'])
                list_item.setInfo(info_type, info)
                if 'thumbnail' in item:
                    list_item.setArt({'icon': item['thumbnail'], 'thumb': item['thumbnail']})
            elif ('image' in item or (item_name_extension and item_name_extension in self._image_file_extensions)) and self._content_type == 'image':
                Logger.debug('image in item: %s' % (Utils.str('image' in item)),)
                Logger.debug('item_name_extension in self._image_file_extensions: %s' % (Utils.str(item_name_extension in self._image_file_extensions),))
                params['action'] = 'download'
                cmd = 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode(params)+')'
                context_options.append((self._common_addon.getLocalizedString(32051), cmd))
                if 'url' in item:
                    url = item['url']
                else:
                    url = self._get_item_play_url(urllib.parse.quote(Utils.str(item_name)), driveid, item_driveid, item_id)
                if 'image' in item:
                    info.update(item['image'])
                list_item.setInfo('pictures', info)
                if 'thumbnail' in item and item['thumbnail']:
                    list_item.setArt({'icon': item['thumbnail'], 'thumb': item['thumbnail']})
            if url:
                context_options.extend(self.get_context_options(list_item, params, is_folder))
                list_item.addContextMenuItems(context_options)
                mimetype = Utils.default(Utils.get_mimetype_by_extension(item_name_extension), Utils.get_safe_value(item, 'mimetype'))
                if mimetype:
                    list_item.setProperty('mimetype', mimetype)
                
                listing.append((url, list_item, is_folder))
        xbmcplugin.addDirectoryItems(self._addon_handle, listing, len(listing))
        xbmcplugin.endOfDirectory(self._addon_handle, True)
    
    def get_context_options(self, list_item, params, is_folder):
        return []
        
    def _search(self, driveid, item_driveid=None, item_id=None):
        self.get_provider().configure(self._account_manager, driveid)
        query = self._dialog.input(self._addon_name + ' - ' + self._common_addon.getLocalizedString(32042))
        if query:
            self._progress_dialog_bg.create(self._addon_name, self._common_addon.getLocalizedString(32041))
            items = self.get_provider().search(query, item_driveid, item_id, on_items_page_completed = self.on_items_page_completed)
            if self.cancel_operation():
                return
            self._process_items(items, driveid)
    
    def download(self, driveid, item_driveid=None, item_id=None):
        dest_folder = self._dialog.browse(0, self._common_addon.getLocalizedString(32002), 'files')
        if dest_folder:
            provider = self.get_provider()
            provider.configure(self._account_manager, driveid)
            item = provider.get_item(item_driveid, item_id, include_download_info=True)
            name = Utils.get_safe_value(item,'name', item['id'])
            download_path = os.path.join(dest_folder, Utils.unicode(name))
            download_size = Utils.get_safe_value(item, 'size', 0)
            on_update_download = lambda request: self._progress_dialog_bg.update(int(1.0*request.download_progress/download_size*100), self._addon_name, self._common_addon.getLocalizedString(32056) % name)
            if ExportManager.download(item, download_path, provider, on_update_download = on_update_download):
                msg = self._common_addon.getLocalizedString(32057) % name
            else:
                msg = self._common_addon.getLocalizedString(32087) % name
            KodiUtils.show_notification(msg)
    
    def new_change_token_slideshow(self, change_token, driveid, item_driveid=None, item_id=None, path=None):
        self.get_provider().configure(self._account_manager, driveid)
        item = self.get_provider().get_item(item_driveid, item_id, path)
        if self.cancel_operation():
            return
        return item['folder']['child_count']
    
    def _slideshow(self, driveid, item_driveid=None, item_id=None, path=None, change_token=None):
        new_change_token = self.new_change_token_slideshow(change_token, driveid, item_driveid, item_id, path)
        if self.cancel_operation():
            return
        wait_for_slideshow = False
        if not change_token or change_token != new_change_token:
            Logger.notice('Slideshow will start. change_token: %s, new_change_token: %s' % (change_token, new_change_token))
            params = {'action':'_list_folder', 'content_type': self._content_type,
                      'item_driveid': Utils.default(item_driveid, ''), 'item_id': Utils.default(item_id, ''), 'driveid': driveid, 'path' : Utils.default(path, '')}
            extra_params = ',recursive' if self._addon.getSetting('slideshow_recursive') == 'true' else ''
            KodiUtils.executebuiltin('SlideShow('+self._addon_url + '?' + urllib.parse.urlencode(params) + extra_params + ')')
            wait_for_slideshow = True
        else:
            Logger.notice('Slideshow child count is the same, nothing to refresh...')
        t = threading.Thread(target=self._refresh_slideshow, args=(driveid, item_driveid, item_id, path, new_change_token, wait_for_slideshow,))
        t.setDaemon(True)
        t.start()
    
    def _refresh_slideshow(self, driveid, item_driveid, item_id, path, change_token, wait_for_slideshow):
        if wait_for_slideshow:
            Logger.notice('Waiting up to 10 minutes until the slideshow for folder %s starts...' % Utils.default(item_id, path))
            max_waiting_time = time.time() + 10 * 60
            while not self.cancel_operation() and not KodiUtils.get_cond_visibility('Slideshow.IsActive') and max_waiting_time > time.time():
                if self._system_monitor.waitForAbort(2):
                    break
            self._print_slideshow_info()
        interval = self._addon.getSetting('slideshow_refresh_interval')
        Logger.notice('Waiting up to %s minute(s) to check if it is needed to refresh the slideshow of folder %s...' % (interval, Utils.default(item_id, path)))
        target_time = time.time() + int(interval) * 60
        while not self.cancel_operation() and target_time > time.time() and KodiUtils.get_cond_visibility('Slideshow.IsActive'):
            if self._system_monitor.waitForAbort(10):
                break
        self._print_slideshow_info()
        if not self.cancel_operation() and KodiUtils.get_cond_visibility('Slideshow.IsActive'):
            try:
                self._slideshow(driveid, item_driveid, item_id, path, change_token)
            except Exception as e:
                Logger.error('Slideshow failed to auto refresh. Will be restarted when possible. Error: ')
                Logger.error(ExceptionUtils.full_stacktrace(e))
                self._refresh_slideshow(driveid, item_driveid, item_id, path, None, wait_for_slideshow)
        else:
            Logger.notice('Slideshow is not running anymore or abort requested.')
        
    def _print_slideshow_info(self):
        if KodiUtils.get_cond_visibility('Slideshow.IsActive'):
            Logger.debug('Slideshow is there...')
        elif self.cancel_operation():
            Logger.debug('Abort requested...')
            
    def _get_item_play_url(self, file_name, driveid, item_driveid=None, item_id=None, is_subtitle=False):
        return DownloadServiceUtil.build_download_url(driveid, item_driveid, item_id, urllib.parse.quote(Utils.str(file_name)))
    
    def play(self, driveid, item_driveid=None, item_id=None):
        self.get_provider().configure(self._account_manager, driveid)
        find_subtitles = self._addon.getSetting('set_subtitle') == 'true' and self._content_type == 'video'
        item = self.get_provider().get_item(item_driveid, item_id, find_subtitles=find_subtitles)
        file_name = Utils.unicode(item['name'])
        list_item = xbmcgui.ListItem(file_name)
        succeeded = True
        info = KodiUtils.get_current_library_info()
        if not info:
            info = KodiUtils.find_exported_video_in_library(item_id, file_name + ExportManager._strm_extension)
        if info and info['id']:
            Logger.debug('library info: %s' % Utils.str(info))
            KodiUtils.set_home_property('dbid', Utils.str(info['id']))
            KodiUtils.set_home_property('dbtype', info['type'])
            KodiUtils.set_home_property('addonid', self._addonid)
            details = KodiUtils.get_video_details(info['type'], info['id'])
            Logger.debug('library details: %s' % Utils.str(details))
            if details and 'resume' in details:
                KodiUtils.set_home_property('playcount', Utils.str(details['playcount']))
                resume = details['resume']
                if resume['position'] > 0:
                    play_resume = False
                    if self.iskrypton:
                        play_resume = KodiUtils.get_addon_setting('resume_playing') == 'true'
                    elif KodiUtils.get_addon_setting('ask_resume') == 'true':
                        d = datetime(1,1,1) + timedelta(seconds=resume['position'])
                        t = '%02d:%02d:%02d' % (d.hour, d.minute, d.second)
                        Logger.debug(t)
                        option = self._dialog.contextmenu([KodiUtils.localize(32054, addon=self._common_addon) % t, KodiUtils.localize(12021)])
                        Logger.debug('selected option: %d' % option)
                        if option == -1:
                            succeeded = False
                        elif option == 0:
                            play_resume = True
                    if play_resume:
                        list_item.setProperty('resumetime', Utils.str(resume['position']))
                        list_item.setProperty('startoffset', Utils.str(resume['position']))
                        list_item.setProperty('totaltime', Utils.str(resume['total']))
        else:
            from resources.lib.vendor.clouddrive_common.service.player import KodiPlayer
            KodiPlayer.cleanup()
        if 'audio' in item:
            list_item.setInfo('music', item['audio'])
        elif 'video' in item:
            list_item.addStreamInfo('video', item['video'])
        list_item.select(True)
        list_item.setPath(self._get_item_play_url(file_name, driveid, item_driveid, item_id))
        list_item.setProperty('mimetype', Utils.get_safe_value(item, 'mimetype'))
        if find_subtitles and 'subtitles' in item:
            subtitles = []
            for subtitle in item['subtitles']:
                subtitles.append(self._get_item_play_url(urllib.parse.quote(Utils.str(subtitle['name'])), driveid, Utils.default(Utils.get_safe_value(subtitle, 'drive_id'), driveid), subtitle['id'], True))
            list_item.setSubtitles(subtitles)
        if not self.cancel_operation():
            xbmcplugin.setResolvedUrl(self._addon_handle, succeeded, list_item)
    
    # One sentence per outcome in resources/lib/auth/errors.py. That module
    # returns a symbolic outcome and a bare code and holds no words at all, so
    # this is the only place the pairing exists in code -- the other copy is the
    # comment above the block in strings.po, which a translator reads. Neither
    # file names the other's contents, and
    # test_every_failure_outcome_renders_its_own_sentence holds the join.
    #
    # The unmapped outcome is deliberately absent: it renders through
    # _FAILURE_UNMAPPED_STRING, which keeps the bare provider code on screen. A
    # code a person can read off a television and quote is worth more than a
    # friendly sentence that hides it.
    _FAILURE_STRINGS = {
        errors.PUBLIC_CLIENT_FLOWS_OFF: 30046,
        errors.CONSENT_REQUIRED: 30047,
        errors.ADMIN_CONSENT_REQUIRED: 30048,
        errors.NOT_ASSIGNED_TO_APPLICATION: 30049,
        errors.BLOCKED_BY_CONDITIONAL_ACCESS: 30050,
        errors.BLOCKED_BY_SECURITY_DEFAULTS: 30051,
        errors.MFA_REQUIRED: 30052,
        errors.MFA_ENROLMENT_REQUIRED: 30053,
        errors.PASSWORD_EXPIRED: 30054,
        errors.APPLICATION_DISABLED: 30055,
        errors.APPLICATION_NOT_IN_TENANT: 30056,
        errors.DEVICE_CODE_REJECTED: 30057,
        errors.DEVICE_CODE_EXPIRED: 30058,
    }
    _FAILURE_UNMAPPED_STRING = 30044
    # Appended to any outcome the table marks administrator-must-act, and to
    # nothing else. It is the only place the expert-level custom identifier
    # setting is named, which is what makes the tenant-block message and that
    # setting one feature rather than two.
    _FAILURE_ESCAPE_HATCH_STRING = 30045

    def _provider_failure(self, rex):
        """The identity provider's own refusal carried by `rex`, or None.

        What arrives here is the transport's report, not the body: the
        exception's response field is assembled by Request with the credential
        fields already cut short. The code survives that, because it lives in
        the description and the description is not a credential.

        The description itself never leaves this method. It is paragraph-length
        and carries formatted links, and rendering it would put
        provider-controlled prose on a television (T-03-44).
        """
        if not rex or not rex.response:
            return None
        text = Utils.str(rex.response)
        failure = errors.classify(text)
        if failure.outcome == errors.UNMAPPED and not failure.code:
            # No code in the description. The error_codes array is the other
            # place the refusal is named, and a proxy that truncates the
            # paragraph leaves the array intact -- so the body is read out of
            # the report and tried the other way before giving up.
            start = text.find('{')
            if start >= 0:
                try:
                    payload = json.loads(text[start:])
                except (TypeError, ValueError):
                    payload = None
                if isinstance(payload, dict):
                    failure = errors.classify_response(payload)
        if failure.outcome == errors.UNMAPPED and not failure.code:
            return None
        return failure

    def _failure_sentence(self, failure):
        string_id = self._FAILURE_STRINGS.get(failure.outcome)
        if string_id is None:
            return self._addon_string(self._FAILURE_UNMAPPED_STRING) % (
                Utils.str(failure.code) or '-')
        sentence = self._addon_string(string_id)
        if failure.admin_must_act:
            sentence += '[CR]' + self._addon_string(
                self._FAILURE_ESCAPE_HATCH_STRING)
        return sentence

    def _offer_signin_again(self, ex, httpex, add_account_cmd):
        """Ask whether to sign in again, if that is what this failure needs.

        True when the offer was made, so the caller can suppress the ordinary
        error dialog. Two triggers, and only two:

        an unauthorised response, which is the surviving half of a branch whose
        other half read the third party's address out of the request; and
        ReauthorisationRequired, which the refresh raises only for the outcome
        it names NEEDS_REAUTHORISATION. A transient refresh failure raises a
        plain RequestException instead and reaches none of this, which is the
        whole of Pitfall E: a refresh that failed because the Wi-Fi was not up
        yet must not sign anybody out.
        """
        unauthorised = httpex is not None and httpex.code == 401
        finished = ExceptionUtils.extract_exception(
            ex, ReauthorisationRequired) is not None
        if not (unauthorised or finished):
            return False

        driveid = Utils.get_safe_value(self._addon_params, 'driveid')
        if not driveid:
            # Nothing names which account this was for, so the prompt cannot be
            # written. The ordinary error dialog is the honest answer.
            return False
        account = self._account_manager.get_by_driveid('account', driveid)
        drive = self._account_manager.get_by_driveid('drive', driveid, account)
        if self._dialog.yesno(self._addon_name,
                              self._common_addon.getLocalizedString(32046)
                              % (self._get_display_name(account, drive, True) + '\n')):
            KodiUtils.executebuiltin(add_account_cmd)
        return True

    def _handle_exception(self, ex, show_error_dialog = True):
        stacktrace = ExceptionUtils.full_stacktrace(ex)
        rex = ExceptionUtils.extract_exception(ex, RequestException)
        uiex = ExceptionUtils.extract_exception(ex, UIException)
        httpex = ExceptionUtils.extract_exception(ex, HTTPError)
        urlex = ExceptionUtils.extract_exception(ex, URLError)
        failure = self._provider_failure(rex)
        line1 = self._common_addon.getLocalizedString(32027)
        line2 = Utils.unicode(ex)
        line3 = self._common_addon.getLocalizedString(32016)

        if uiex:
            line1 = self._common_addon.getLocalizedString(int(Utils.str(uiex)))
            line2 = Utils.unicode(uiex.root_exception)
        elif rex and rex.response:
            line1 += ' ' + Utils.unicode(rex)
            line2 = ExceptionUtils.extract_error_message(rex.response)
        add_account_cmd = 'RunPlugin('+self._addon_url + '?' + urllib.parse.urlencode({'action':'_add_account', 'content_type': self._content_type})+')'
        if isinstance(ex, AccountNotFoundException) or isinstance(ex, DriveNotFoundException):
            show_error_dialog = False
            if self._dialog.yesno(self._addon_name, self._common_addon.getLocalizedString(32063) % '\n'):
                KodiUtils.executebuiltin(add_account_cmd)
        elif self._offer_signin_again(ex, httpex, add_account_cmd):
            # An unauthorised response, or a refresh whose grant is finished.
            # Both mean the same thing to the person in front of the television
            # and both offer the one action that helps.
            #
            # The branch that stood here also treated the third party's address
            # appearing in the request as this signal. That address is gone, and
            # so is the half that looked for it; the unauthorised half survives,
            # because it is a genuine re-authorisation trigger.
            show_error_dialog = False
        elif failure:
            # A refusal by the identity provider, rendered as the sentence its
            # code maps to, with the escape hatch appended when no retry can
            # clear it (AUTH-18). The provider's own description is never shown:
            # it is paragraph-length with formatted links (T-03-44).
            Logger.error('provider refusal: %s (%s)'
                         % (failure.outcome, failure.code or 'no code'))
            line1 = self._failure_sentence(failure)
            line2 = line3 = None
        elif rex and httpex:
            if httpex.code >= 500:
                line1 = self._common_addon.getLocalizedString(32035)
                line2 = None
                line3 = self._common_addon.getLocalizedString(32038)
            elif httpex.code >= 400:
                driveid = Utils.get_safe_value(self._addon_params, 'driveid')
                if driveid:
                    if httpex.code == 403:
                        line1 = self._common_addon.getLocalizedString(32019)
                        line2 = line3 = None
                    elif httpex.code == 404:
                        line1 = self._common_addon.getLocalizedString(32037)
                        line2 = None
                    else:
                        line1 = self._common_addon.getLocalizedString(32036)
                        line3 = self._common_addon.getLocalizedString(32038)
                # The address-changed heuristic that stood here is gone with
                # the third party it questioned. It compared the address seen
                # before the code was issued against one fetched a second time
                # from inside the failure handler -- a second live request to
                # the same third party, made while reporting a failure. Both
                # ends of the comparison were that server; neither exists now.
                # Strings 32072 and 32073 are orphaned by this.
        elif urlex:
            reason = Utils.str(urlex.reason)
            line3 = self._common_addon.getLocalizedString(32074)
            if '[Errno 101]' in reason:
                line1 = self._common_addon.getLocalizedString(32076)
            elif '[Errno 11001]' in reason:
                line1 = self._common_addon.getLocalizedString(32077)
            elif 'CERTIFICATE_VERIFY_FAILED' in reason:
                line1 = self._common_addon.getLocalizedString(32078)
            else:
                line1 = self._common_addon.getLocalizedString(32075)
            
        report = '[%s] [%s]/[%s]\n\n%s\n%s\n%s\n\n%s' % (self._addonid, self._addon_version, self._common_addon_version, line1, line2, line3, stacktrace)
        if rex:
            # Through the transport's redactor, not around it. What stood here
            # concatenated the request and the response straight into a string
            # that goes to a log file users paste into public forums verbatim,
            # and a failing token exchange answers with a body that IS the
            # credential -- a refresh token and a device code, in the clear,
            # every time sign-in went wrong (D-06, T-03-41).
            #
            # These two fields are the transport's own reports and are already
            # redacted at their source, so this is a second pass. It is not
            # theatre: this handler is reachable with a RequestException any
            # caller can construct, and the redactor at the point of writing is
            # the one place that covers those too. The pass is idempotent -- a
            # value already cut to eight characters and a marker comes back
            # unchanged.
            report += '\n\n%s\nResponse:\n%s' % (
                Request.get_body_for_report(rex.request),
                Request.get_body_for_report(rex.response))
        report += '\n\nshow_error_dialog: %s' % show_error_dialog
        Logger.error(report)
        if show_error_dialog:
            if line2:
                line1 += '\n' + line2
            if line3:
                line1 += '\n' + line3
            self._dialog.ok(self._addon_name, line1)
        # The prompt inviting the user to send this report to a third party
        # stood here, together with the two settings that remembered the answer
        # and the call that sent it. All three are gone with the reporter. The
        # report is written to the log and goes nowhere else (AUTH-23, T-03-42).


    def _open_common_settings(self):
        self._common_addon.openSettings()
    
    def _clear_cache(self):
        Cache(self._addonid, 'page', 0).clear()
        Cache(self._addonid, 'children', 0).clear()
        Cache(self._addonid, 'items', 0).clear()
        
    def _rename_action(self):
        pass

    def _action_map(self):
        """Every action a plugin address may name, written down.

        A plugin:// address is not a trusted input. A favourite, a stored
        playlist entry, a keymap or another installed add-on can construct one,
        and nothing on this side can tell which did. What stood here looked the
        method up by name on `self`, so the address chose which method ran out
        of everything the class and its bases happened to define -- including
        every private helper and every method a future edit adds (T-03-40).

        A stop-list on names would not fix it, and it is worth saying why,
        because a stop-list is the cheaper-looking answer. The namespace it
        would filter grows every time somebody adds a method: each addition
        silently gains an entry point, and nobody reviewing that addition is
        looking at the router. This mapping gains nothing when a method is
        added. That asymmetry is the whole argument.

        The keys are derived, not recalled: `test_every_constructed_action_is_
        routable` sweeps the tree for every literal this add-on writes into an
        address of its own and asserts each one is here. Aliases are not -- the
        three friendly names live in `_rename_action`, which runs first, so this
        table stays a plain name-to-method list a reader can check by eye.

        Deliberately absent: `_open_common_settings`. Nothing constructs an
        address for it and `test_vendor_gates` asserts no settings row does,
        because the separate module whose settings it opened no longer exists.
        """
        actions = {
            '_add_account': self._add_account,
            '_reauthorise_account': self._reauthorise_account,
            '_remove_account': self._remove_account,
            '_list_drive': self._list_drive,
            '_list_folder': self._list_folder,
            '_list_exports': self._list_exports,
            '_open_export': self._open_export,
            '_run_export': self._run_export,
            '_remove_export': self._remove_export,
            '_search': self._search,
            '_slideshow': self._slideshow,
            '_clear_cache': self._clear_cache,
            'play': self.play,
            'download': self.download,
        }
        return actions

    def route(self):
        try:
            Logger.debug(self._addon_params)
            self._action = Utils.get_safe_value(self._addon_params, 'action')
            if self._action:
                # Rewriting first, lookup second -- the same order the dynamic
                # lookup ran in, so the three friendly names keep working.
                self._rename_action()
                actions = self._action_map()
                method = actions.get(self._action)
                if method is None:
                    # The ordinary failure path, not a call. It reaches
                    # _handle_exception below, which shows the add-on's usual
                    # error dialog; an unmapped name is either a stale favourite
                    # or somebody probing, and neither deserves a call.
                    raise UIException(32027, Exception(
                        'unroutable action: %s' % Utils.str(self._action)))
                # Binding by introspection is fine now that the method was not
                # chosen by an untrusted string: the name decides which entry of
                # the table above runs, and only the arguments that entry
                # declares are taken from the address.
                arguments = {}
                for name in inspect.getfullargspec(method)[0]:
                    if name in self._addon_params:
                        arguments[name] = self._addon_params[name]
                method(**arguments)
            else:
                self.list_accounts()
        except Exception as ex:
            self._handle_exception(ex)
        finally:
            self._progress_dialog.close()
            self._progress_dialog_bg.close()
            if self._pin_dialog:
                self._pin_dialog.close()
