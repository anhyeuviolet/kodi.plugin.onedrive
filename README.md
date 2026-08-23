# OneDrive KN

A Kodi add-on for playing media from Microsoft OneDrive.

It is a self-contained fork of `plugin.onedrive` by Carlos Guzman (cguZZman). It ships under its
own add-on id, `plugin.onedrive.kn`, so it installs alongside the original without touching it,
its settings or its stored accounts.

## Status

Early. The add-on installs and runs on its own, every screen it has renders, and sign-in now talks
to Microsoft and to nobody else.

**Signing in.** Pick *Add account*. The add-on asks Microsoft for a device code and shows it on the
television, next to the address to enter it at and a QR code for that same address. You open the
address on your phone, type the code, and finish signing in there — on Microsoft's own pages, so the
add-on never sees your password. The television counts the code down while it waits, and offers a
fresh one if it expires. Afterwards the add-on holds a refresh token in its own profile directory
and renews it by itself — once when Kodi starts, and again whenever a request needs a fresher one.

No server other than Microsoft's takes part. The application identifier shipped in the source is
public on purpose: this is the OAuth 2.0 device authorization grant (RFC 8628), which is for
programs running on someone else's machine and therefore unable to keep a secret. The identifier
says which program is asking and authorises nothing on its own. The reasoning, the registration it
names and how to recreate it are in [docs/AZURE-REGISTRATION.md](docs/AZURE-REGISTRATION.md). If
your organisation blocks that registration, you can paste your own in Settings → Expert.

**What that replaced.** The original add-on posted to a third-party sign-in server,
`drive-login.herokuapp.com`: it issued the code, you completed the Microsoft login in a browser, and
it handed the tokens back. That is history now — nothing in this add-on reaches it, and the setting
that pointed at it is gone. It was removed because someone else's server sat in the middle of every
account connection, not because it had stopped working: it was still answering when it was measured
on 2026-08-22.

Until you sign in, a fresh install shows an empty account list. That is the correct result, not a
failure.

The flow above is covered by tests, and the protocol itself was run against Microsoft three times in
a standalone spike, on a work/school account and on a personal one. The add-on in this shape has not
yet been signed in on the television; that is the next piece of work.

## What makes it different from the original

- **Sign-in has no middleman.** The device authorization grant goes straight to Microsoft. The
  original routed it through a server run by someone else, which saw every account being connected.
- **No external dependencies.** The Cloud Drive common module and the QR encoder are bundled
  rather than required, so the only thing this add-on needs is `xbmc.python` 3.0.1. There is no
  separate module add-on to install and no shared code that another add-on's update can change
  underneath it.
- **A separate identity.** New id, new profile directory, new settings store. Installing this does
  not disturb an existing `plugin.onedrive` install.
- **No stored data is executed.** The account and cache databases are read as JSON. The original
  evaluated stored rows as Python source.
- **Network calls are bounded.** The outbound HTTP call carries an explicit timeout.
- **The local directory-listing server is off by default** and is on its way out entirely. It
  served an index of the whole drive on a loopback port with no authorisation check of any kind,
  which on Android means every installed application could read it.

## Requirements

Kodi 20 (Nexus), 21 (Omega) or 22 (Piers). Kodi 19 and earlier are not supported and the add-on
will refuse to install on them.

## Building and installing

Build the archive from a checkout:

```
python tools/build_addon_zip.py
```

It writes `dist/plugin.onedrive.kn-1.0.0.zip`. The name is read out of `addon.xml`, so it follows
the version there rather than being written down twice. The archive holds only what is in the git
index and only what ships: the planning record, the test suite and the build tool itself are left
out.

Get that file onto the television — a USB stick, or a share added in Kodi's own **File manager** —
then install it with **Add-ons → Install from zip file**. Kodi refuses that until
**Settings → System → Add-ons → Unknown sources** is on.

## Attribution

This add-on is not original work. It is a fork of **`plugin.onedrive`** by **Carlos Guzman**
(cguZZman), GPL-3.0-or-later, and it bundles his **`script.module.clouddrive.common`** under the
same licence, **PyQRCode** by **Michael Nooner** under BSD-3-Clause, and **pypng** by
**Johann C. Rocholl** and others under MIT.

The full attribution list is in [CREDITS.md](CREDITS.md). Where the bundled code came from, what
was left out of the copy and every local change to it are recorded in [VENDORED.md](VENDORED.md).

## Maintainer notes

The add-on signs in with an application identifier that is registered with Microsoft outside this
repository. That registration is the only part of the system a fresh clone cannot rebuild, so how it
is configured, how to recreate it and what to do if it lapses are written down in
[docs/AZURE-REGISTRATION.md](docs/AZURE-REGISTRATION.md).

## Licence

GPL-3.0-or-later. See [LICENSE.txt](LICENSE.txt).

This program is not affiliated with or sponsored by Microsoft.
