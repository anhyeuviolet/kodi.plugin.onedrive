# Credits

This add-on is not original work. It is a fork that bundles three other people's code, and every
piece of it is listed here with its licence.

## Origin

**`plugin.onedrive` — OneDrive for Kodi**, by **Carlos Guzman** (cguZZman), licensed
**GPL-3.0-or-later**. This add-on is a fork of it and shares its history. Almost everything outside
the vendored directories is his code, and the per-file copyright headers throughout the tree are
his.

Original project: `https://github.com/cguZZman/plugin.onedrive`

## Bundled: the Cloud Drive common module

**`script.module.clouddrive.common` — Cloud Drive Common Module for Kodi**, by the same author,
**Carlos Guzman** (cguZZman), licensed **GPL-3.0-or-later**.

The original add-on depended on this as a separate Kodi module. This add-on carries a copy of it
instead, at `resources/lib/vendor/clouddrive_common/`. Every file keeps its original copyright
header. See `VENDORED.md` for the exact upstream commit, the exclusion list and every local
modification.

Original project: `https://github.com/cguZZman/script.module.clouddrive.common`

A file named `LICENSE` containing **Apache-2.0** boilerplate sits beside the cache module at
`resources/lib/vendor/clouddrive_common/cache/LICENSE`. It arrived with the module and is preserved
verbatim. Its copyright placeholder was never filled in, so it names nobody, while the module file
next to it carries a GPL-3.0 header by the module's own author. **What that file covers is
unresolved**, and this record does not resolve it by guessing — see `VENDORED.md`.

## Bundled: the QR encoder

**PyQRCode**, by **Michael Nooner**, Copyright (c) 2013, licensed **BSD-3-Clause**.

Carried at `resources/lib/vendor/pyqrcode/`, with the notice in
`resources/lib/vendor/pyqrcode/LICENSE.md`. It renders the QR code shown during sign-in.

Original project: `https://github.com/mnooner256/pyqrcode` — where the code comes from.

**Where this copy comes from is a different place**, and the distinction matters to anyone trying to
re-derive it: the files here were taken from the Kodi add-on zip `script.module.pyqrcode` version
`1.2.1+matrix.4`, published on `mirrors.kodi.tv`, not from the GitHub project above. That zip is the
build this add-on was tested against and the only distribution that bundles the PNG writer. Copying
from GitHub instead yields different bytes. The zip's URL, its sha256 and the per-file hashes are in
`VENDORED.md`.

## Bundled inside the QR encoder: the PNG writer

**pypng**, by **Johann C. Rocholl** and others, Copyright (C) 2006, licensed **MIT**.

PyQRCode bundles it to write the QR image out as a PNG. It is carried at
`resources/lib/vendor/pyqrcode/png.py`, and the notice is the header inside that file.

## Licence of the whole

The combined work is **GPL-3.0-or-later**, because the bundled Cloud Drive common module is. The
full text is in `LICENSE.txt` at the root of this repository. The BSD-3-Clause and MIT components
above are compatible with it and keep their own notices.

## Not affiliated

This program is not affiliated with or sponsored by Microsoft.
