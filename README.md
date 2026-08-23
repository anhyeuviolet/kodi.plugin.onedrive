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

### What the repository does, and what it does not

There is a self-hosted repository for this add-on. **It does not remove the USB stick.** It removes
every USB stick after the first.

Adding a repository to Kodi means installing the repository add-on, and a repository add-on is a
zip like any other — so the first install still goes over whatever route already works on your
television. What changes is everything afterwards: once that one zip is in, Kodi knows where to
look, and new versions arrive over the network on its own schedule with nothing carried by hand.

Two things about this specific television were measured during the Phase 3 acceptance run on a TCL
running Android TV 12 with Kodi 21.2, and both bear on how the first zip gets there:

- **Installing from a URL does not work.** It was tried. Kodi's *add source* browse wants a
  directory listing, and a plain file URL does not provide one. Pointing it at the repository is
  not a way round this, for the reason above: adding a repository is itself a zip install.
- **Kodi could not see files on the USB drive at all** until its Android file permission was
  changed. Folders listed; the files inside them did not. See the section below — it is the single
  most expensive thing on this page to rediscover.

So: one USB trip, then the network.

### Step one, once — the repository add-on

Build both archives from a checkout:

```
python tools/build_addon_zip.py    # dist/plugin.onedrive.kn-1.0.0.zip
python tools/build_repo.py         # dist/pages/ — the whole publishable tree
```

Neither name is written down twice: both are read out of the relevant `addon.xml`, so they follow
the version declared there. The add-on archive holds only what is in the git index and only what
ships — the planning record, the test suite and the build tools themselves are left out, as is the
repository add-on's own source.

Take `dist/pages/repo/repository.onedrive.kn/repository.onedrive.kn-1.0.0.zip` to the television on
a USB stick, or through a share added in Kodi's own **File manager**, and install it with
**Add-ons → Install from zip file**. Kodi refuses that until **Settings → System → Add-ons →
Unknown sources** is on.

### Step two, from then on — everything over the network

**Add-ons → Install from repository → OneDrive KN Repository → Video add-ons → OneDrive KN.** It is
listed under Music and Picture add-ons too — `addon.xml` declares all three — so whichever of the
three you open, it is there.

After that, Kodi polls the repository by itself. Its check is periodic rather than immediate, so a
freshly published version does not appear the same minute; **Add-ons → Check for updates** forces
it if you are impatient.

*Not yet confirmed on hardware.* Everything above is built and tested, but no part of it has been
installed on a television. Whether the unattended update actually arrives without anyone pressing
"check for updates" is the one claim here that only the television can settle, and it has not been
asked yet.

### On Android: if Kodi shows the folders on your USB drive but none of the files

Give Kodi's Android file permission the **"Allow all the time"** setting, not "Allow only while
using the app": Android **Settings → Apps → Kodi → Permissions → Files and media**. Then browse to
the drive again and the zip will be there.

Under the default permission Kodi lists **directories** on external storage and shows **no files
inside them at all**. There is no error, no prompt and nothing in the interface that mentions a
permission — an empty listing looks exactly like an empty folder, which is why this costs a
debugging session rather than a moment. Seen on a TCL television running Android TV 12 with Kodi
21.2, and it stopped the install until the permission was changed.

### Publishing a new version

1. Raise `version` in `addon.xml`, and add a `<news>` entry under it — Kodi shows that text as the
   changelog for the new version, so it is the only place a user reads what changed. Keep the
   version plain: `1.0.1`, never `1.0.1-beta`. Kodi compares versions Debian-style and sorts a
   pre-release suffix *below* the plain version, so a published pre-release can never be superseded
   by the release it precedes. `tools/build_repo.py` refuses to publish one rather than let this
   happen quietly.
2. Run `python tools/build_repo.py`. It rebuilds `dist/pages/` from nothing every time, so there is
   nothing to clean up and two runs of the same commit produce identical bytes.
3. Copy the **contents** of `dist/pages/` to the root of whatever GitHub Pages serves. The
   directory mirrors the URL path exactly, which is what makes this a copy rather than a decision.
4. Do not raise the repository add-on's own version unless one of its URLs changed. Kodi caches the
   repository definition, so a URL change needs a version bump to take effect; nothing else does.
   Team Kodi keep the same warning as a comment in their own repository add-on's manifest.

The published tree is:

```
repo/addons.xml                                                  the index Kodi polls
repo/addons.xml.sha256                                           its digest
repo/plugin.onedrive.kn/plugin.onedrive.kn-<version>.zip         the add-on
repo/plugin.onedrive.kn/plugin.onedrive.kn-<version>.zip.sha256
repo/plugin.onedrive.kn/icon.png
repo/plugin.onedrive.kn/fanart.jpg
repo/repository.onedrive.kn/repository.onedrive.kn-<version>.zip the repository add-on
repo/repository.onedrive.kn/repository.onedrive.kn-<version>.zip.sha256
repo/repository.onedrive.kn/icon.png
```

and `repository.onedrive.kn/addon.xml` declares, at
`https://anhyeuviolet.github.io/kodi.plugin.onedrive/`:

| Element | Value |
|---------|-------|
| `<info>` | `https://anhyeuviolet.github.io/kodi.plugin.onedrive/repo/addons.xml` |
| `<checksum verify="sha256">` | `https://anhyeuviolet.github.io/kodi.plugin.onedrive/repo/addons.xml.sha256` |
| `<datadir>` | `https://anhyeuviolet.github.io/kodi.plugin.onedrive/repo` |
| `<hashes>` | `sha256` |

Those four values are the only place the layout is written. `tools/build_repo.py` reads them and
derives every path it writes, and `tests/test_build_repo.py` asserts that each declared URL is
answered by a real file. A repository whose declared address and real tree disagree installs, says
nothing, and finds nothing — there is no screen in Kodi that reports it.

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
