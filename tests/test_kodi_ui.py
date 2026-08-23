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
"""The two places a deliberate defect left the suite green.

Phase 3's verification injected twenty-one defects into shipped source. Nineteen
turned a named test red. These two did not:

  * deleting the "Add an account..." row from `list_accounts` -- the only route
    into sign-in on a fresh install, so losing it makes the add-on impossible to
    sign into at all;
  * renaming `_is_secure_url` out from under its call site in `QRDialogProgress`
    -- the refusal to encode a non-https sign-in address into an image a person
    is instructed to point a camera at.

Both are here rather than in `tests/test_auth_gates.py`, and both are driven
rather than swept, for the same reason. A gate reads source text, and neither of
these properties is a fact about source text: the first is about what the listing
the user is shown *contains*, and the second is about whether an image is
*produced*. A sweep for the string `_is_secure_url` would pass on a call site
whose guard had been inverted, and would fail on a rename that renamed both ends
correctly -- exactly backwards in both directions. So these run the code.

The Kodi modules come from `tests/kodistub.py`, which puts `sys.modules` back on
the way out and asserts that it did.
"""

import os


from kodistub import kodi_stubs


# The catalogue id the vendored module gives the add-account row. The row's
# label is asserted through this id rather than through the English words, so a
# translation cannot fail the test and deleting the row still can.
ADD_ACCOUNT_STRING_ID = 32005

ADD_ACCOUNT_ACTION = '_add_account'


def _account_list(recorder, accounts):
    """Run `list_accounts` against `accounts` and return what Kodi was handed.

    The instance is built with `object.__new__` and given the five attributes
    the method reads. Calling the real `__init__` would require `sys.argv` to be
    a plugin invocation and would drag in an account manager, a provider and a
    settings object -- none of which this question is about. `get_accounts` is
    replaced on the instance because it is the seam where stored accounts enter;
    everything below it, including `_needs_reauthorisation` and `_addon_string`,
    is the real method.
    """
    from resources.lib.vendor.clouddrive_common.ui.addon import CloudDriveAddon
    import xbmcaddon

    addon = object.__new__(CloudDriveAddon)
    addon._addon = xbmcaddon.Addon()
    addon._common_addon = xbmcaddon.Addon()
    addon._addon_url = 'plugin://plugin.onedrive.kn/'
    addon._addon_handle = 1
    addon._content_type = 'video'
    addon.get_accounts = lambda with_format=False: accounts
    # `__del__` deletes seven attributes unconditionally. It runs when this
    # object is collected, after the assertions, and a missing attribute there
    # raises inside a destructor -- which the interpreter swallows and pytest
    # then reports as an unraisable warning against whichever test happened to
    # be running. Supplying them keeps the failure signal clean.
    for unused in ('_dialog', '_progress_dialog', '_progress_dialog_bg',
                   '_system_monitor', '_account_manager'):
        setattr(addon, unused, None)

    addon.list_accounts()

    assert recorder.directory_items is not None, (
        'list_accounts never called addDirectoryItems, so this test is reading '
        'nothing and certifies nothing')
    return recorder.directory_items


def _urls(items):
    return [item[0] for item in items]


def _one_account():
    return {
        'account-1': {
            'id': 'account-1',
            'drives': [{'id': 'drive-1', 'display_name': 'Kenny Nguyen'}],
        },
    }


# ---------------------------------------------------------------------------
# The "Add an account..." row (AUTH-22, first clause)
# ---------------------------------------------------------------------------
#
# On a fresh install the account list is empty, and this row is the only item in
# it. There is no other route to _add_account: the action is never reached from
# a context menu, from a settings row, or from a plugin address a user could
# type. Delete the row and the add-on is a directory that lists nothing and can
# never be made to list anything -- which is not a degraded feature, it is the
# whole add-on -- and before this test nothing in the suite failed.
#
# Asserted twice, empty and populated, because the deletion that matters is of
# the three lines *after* the account loop. A test that only looked at the empty
# case would pass on a listing that offered the row when there was nothing else
# and dropped it the moment a first account existed, which is the harder failure
# to notice and the one that strands a user who removes their only account.

def test_the_account_list_always_offers_a_route_into_sign_in(tmp_path):
    with kodi_stubs(tmp_path / 'profile') as recorder:
        empty = _account_list(recorder, {})

        assert len(empty) == 1, (
            'a fresh install with no accounts produced %d row(s): %r. It must '
            'produce exactly one, the add-account row, because that row is the '
            'only route into sign-in that exists'
            % (len(empty), _urls(empty)))
        assert ADD_ACCOUNT_ACTION in empty[0][0], (
            'the only row on a fresh install does not reach %s. Its address is '
            '%r, so the add-on cannot be signed into at all'
            % (ADD_ACCOUNT_ACTION, empty[0][0]))

    with kodi_stubs(tmp_path / 'profile2') as recorder:
        populated = _account_list(recorder, _one_account())

        offering = [url for url in _urls(populated)
                    if ADD_ACCOUNT_ACTION in url]
        assert offering, (
            'an account list holding one account offers no add-account row. '
            'The %d row(s) built were %r, so a second account can never be '
            'added and a user who removes their only one is stranded'
            % (len(populated), _urls(populated)))

        # Non-vacuity: the account itself is in the listing, so the assertion
        # above is not passing on a listing that happens to contain one item
        # because the account loop silently produced nothing.
        account_rows = [url for url in _urls(populated)
                        if 'driveid=drive-1' in url]
        assert account_rows, (
            'the one stored account produced no row of its own, so this test '
            'is not reading a real account list: %r' % (_urls(populated),))


def test_the_add_account_row_is_labelled_from_the_catalogue(tmp_path):
    """The row carries the catalogue's words, not a literal.

    Separate from the routing assertion above because it fails for a different
    reason and should say so: a row that is present and addressed correctly but
    labelled from a hardcoded English string is a translation defect, not a
    dead end.
    """
    with kodi_stubs(tmp_path / 'profile') as recorder:
        import xbmcaddon

        expected = xbmcaddon.Addon().getLocalizedString(ADD_ACCOUNT_STRING_ID)
        items = _account_list(recorder, {})

        labels = [item[1].label for item in items]
        assert expected in labels, (
            'no row is labelled from catalogue string %d. The labels built '
            'were %r, so either the add-account row is gone or its label is a '
            'literal that no translation can reach'
            % (ADD_ACCOUNT_STRING_ID, labels))


# ---------------------------------------------------------------------------
# The QR's https refusal (AUTH-08, second clause)
# ---------------------------------------------------------------------------
#
# `QRDialogProgress.onInit` encodes the sign-in address into a PNG only when
# `_is_secure_url` says the address is https with a host. A QR is a thing a
# person is told to point a camera at, and it is read by a device that will open
# whatever it finds without showing anyone the address first, so an image is the
# one place a downgraded address is least likely to be noticed.
#
# Driven, not swept. The mutation that motivated these two tests renamed
# `_is_secure_url` and left the call site alone, which raises AttributeError
# inside onInit and turns both of them red; but a guard rewritten to `if True`
# renames nothing and would defeat any sweep, and turns the first of them red
# just the same. The second test is the non-vacuity guard for the first: without
# it, "no image was written" would also pass on an encoder that had stopped
# working entirely.

def _drive_on_init(qr_code):
    """Run `QRDialogProgress.onInit` and report the controls it touched."""
    from resources.lib.vendor.clouddrive_common.ui.dialog import QRDialogProgress
    from kodistub import Control

    dialog = object.__new__(QRDialogProgress)
    QRDialogProgress.__init__(
        dialog, 'pin-dialog.xml', '.', 'default',
        heading='Sign in', qr_code=qr_code,
        line1='one', line2='two', line3='three', code='K7QF3NBXZ')

    controls = {}

    def get_control(control_id):
        return controls.setdefault(control_id, Control(control_id))

    dialog.getControl = get_control
    dialog.setFocus = lambda control: None

    dialog.onInit()
    return dialog, controls


def test_the_qr_refuses_a_sign_in_address_that_is_not_https(tmp_path):
    profile = tmp_path / 'profile'
    with kodi_stubs(profile):
        from resources.lib.vendor.clouddrive_common.ui.dialog import QRDialogProgress

        dialog, controls = _drive_on_init('http://login.microsoft.com/device')

        # Evidence that onInit really ran, before anything is concluded from
        # what it did not do. A refusal and a dialog that never initialised at
        # all produce the same empty profile directory, and only one of them is
        # the property being asserted.
        code_control = controls.get(QRDialogProgress._code_control)
        assert code_control is not None and code_control.label == 'K7QF3NBXZ', (
            'onInit did not put the code on the screen, so it did not run far '
            'enough for the absence of an image to mean anything')

        # The refusal branch never asks for the QR control at all -- there is
        # nothing to put in it -- so its absence is a pass. What must not have
        # happened is an image reaching it.
        qr_control = controls.get(QRDialogProgress._qr_control)
        assert qr_control is None or qr_control.image is None, (
            'an http:// sign-in address was encoded into a QR image at %r. A '
            'person is instructed to point a camera at that image and the '
            'device opens what it finds without showing the address first'
            % (qr_control.image,))
        assert dialog._image_path is None, (
            'the dialog recorded an image path (%r) for an insecure address, '
            'so something was written even though the control was not set'
            % (dialog._image_path,))

        written = []
        if os.path.isdir(str(profile)):
            written = [name for name in os.listdir(str(profile))
                       if name.startswith('qr-')]
        assert not written, (
            'a QR image file was written for an insecure address: %r' % (written,))

        # The refusal drops the image and nothing else: the panel still renders
        # its body text, so a user reading the code off the screen is unaffected
        # by an address the encoder would not touch.
        text_control = controls.get(QRDialogProgress._text_control)
        assert text_control is not None and text_control.text, (
            'refusing the address also left the dialog body empty, so the '
            'refusal took the panel down rather than dropping one control')


def test_the_qr_encodes_a_secure_sign_in_address(tmp_path):
    """The other half, and the reason the refusal test means anything.

    Without this, an encoder that had stopped producing images under every
    condition would leave the test above green.
    """
    profile = tmp_path / 'profile'
    with kodi_stubs(profile):
        from resources.lib.vendor.clouddrive_common.ui.dialog import QRDialogProgress

        dialog, controls = _drive_on_init('https://login.microsoft.com/device')

        qr_control = controls[QRDialogProgress._qr_control]
        assert qr_control.image, (
            'a valid https sign-in address produced no QR image, so the '
            'refusal test above is passing on an encoder that never encodes '
            'anything')
        assert qr_control.image == dialog._image_path
        assert os.path.isfile(dialog._image_path), (
            'the QR control was pointed at %r and no file is there'
            % (dialog._image_path,))
        assert os.path.getsize(dialog._image_path) > 0

        # The per-invocation name, which is what stops Kodi's path-keyed texture
        # cache from rendering the previous code against a new one.
        assert os.path.basename(dialog._image_path).startswith('qr-')
