# OneDrive KN

A Kodi add-on for playing media from Microsoft OneDrive.

It is a self-contained fork of `plugin.onedrive` by Carlos Guzman (cguZZman). It ships under its
own add-on id, `plugin.onedrive.kn`, so it installs alongside the original without touching it,
its settings or its stored accounts.

## Status

**Sign-in does not work in this build, so nothing behind it works either.** The original add-on
signs in through a third-party broker service that has been offline since November 2022. That
problem is inherited, not introduced here. A device-code sign-in flow that talks to Microsoft
directly is the next piece of work; until it lands, a fresh install shows an empty account list and
there is nothing to browse or play.

What is done: the add-on is self-contained and installs on its own.

## What makes it different from the original

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

## Installing

Download or build a zip of this repository, then in Kodi:
**Add-ons → Install from zip file**.

## Attribution

This add-on is not original work. It is a fork of **`plugin.onedrive`** by **Carlos Guzman**
(cguZZman), GPL-3.0-or-later, and it bundles his **`script.module.clouddrive.common`** under the
same licence, **PyQRCode** by **Michael Nooner** under BSD-3-Clause, and **pypng** by
**Johann C. Rocholl** and others under MIT.

The full attribution list is in [CREDITS.md](CREDITS.md). Where the bundled code came from, what
was left out of the copy and every local change to it are recorded in [VENDORED.md](VENDORED.md).

## Licence

GPL-3.0-or-later. See [LICENSE.txt](LICENSE.txt).

This program is not affiliated with or sponsored by Microsoft.
