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
"""The layering gate: where a Kodi import is allowed to happen at import time.

`CI-01` says one directory may import `xbmc*` at module level, and it names
`resources/lib/kodi/`. Everything else in this tree either does not touch Kodi
at all -- `resources/lib/auth/` and `resources/lib/graph/` are the two packages
whose tests need no stub library, which is the whole point of them -- or reaches
Kodi from inside a function, where the import happens when the function runs and
not when the module is read.

The requirement existed for fourteen plans with nothing holding it, and in that
time a module that imports `xbmc` at module level was added one directory above
the only place it is permitted. That is deferred item 17, and it is what this
file is for: a boundary with no test is not a boundary.

Nothing here imports a Kodi module, so it needs no stub library and no fixtures.
Failures report path and line number, never a bare count: a count cannot be
acted on. The sweep carries an explicit non-vacuity guard, because a sweep that
passes because it found nothing certifies nothing.
"""

import ast

# The repository root, the index-backed file list and the failure report all
# live in gatelib, because this is not the only gate file. Two copies of the
# exclusion set drift; one does not.
from gatelib import (
    REPO,
    python_sources,
    read as _read,
    report as _report,
    tracked_files,
)

# The one directory CI-01 permits, written as a prefix with its trailing
# separator. Without the separator a sibling directory whose name merely starts
# with the same characters -- `resources/lib/kodideprecated/`, say -- would be
# dropped from the offender set by accident, and the boundary would be wider
# than the requirement it enforces by a name nobody chose.
KODI_ADAPTER_DIR = 'resources/lib/kodi/'

# The vendored tree is kept byte-identical to upstream except where VENDORED.md
# records a change, so that a regression can be attributed to upstream or to us
# rather than argued about. These two files are Kodi from their first line by
# design -- they are the UI layer of a Kodi add-on framework -- and moving their
# imports would be a modification made for a gate's convenience rather than for
# the add-on, which is the one reason this repository does not modify a vendored
# file.
#
# Each row names one exact tracked path and the reason that pays for it, in the
# shape FOREIGN_NOTICES uses in the sibling gate file. Adding a row is therefore
# a stricter demand and never a silent escape hatch: the path must exist, the
# file must currently have a module-level Kodi import, and the reason must be
# there to read. Like the exclusion sets, this lives here and nowhere else.
MODULE_LEVEL_KODI_EXEMPTIONS = {
    'resources/lib/vendor/clouddrive_common/ui/addon.py':
        'vendored UI layer, unmodified from upstream except where VENDORED.md '
        'records it; xbmcgui, xbmcplugin and xbmcvfs are imported at the top of '
        'the file by upstream and this repository does not rewrite a vendored '
        'import to suit a gate',
    'resources/lib/vendor/clouddrive_common/ui/dialog.py':
        'vendored dialog layer, same reason; it subclasses '
        'xbmcgui.WindowXMLDialog, so the module cannot be read at all without '
        'xbmcgui and there is no in-function form of that dependency',
}


def module_level_kodi_imports(rel):
    """Every (path, lineno, name) where `rel` imports Kodi at import time.

    PARSED, not swept, for the same reason the urllib-submodule gate parses: a
    regular expression over the text would prove that the line `import xbmc`
    appears somewhere in the file, which is not the thing CI-01 is about. What
    matters is whether the import *runs when the module is read*, because that
    is what makes the module unloadable on a host with no Kodi installed and
    therefore untestable without a stub library. A module that imports Kodi
    inside a function is fine and a naive sweep flags it anyway.

    Neither of the two obvious AST shortcuts is correct either:

      * A loop over `tree.body` alone would miss a module-level
        `try: import xbmc / except ImportError:`, because the `Import` node
        sits inside a `Try` node rather than in the module body. So this
        descends into `Try`, `If` and `With`, and into their `orelse`,
        `finalbody` and `handlers` bodies as well -- everything reachable
        without entering a function or a class runs at import.
      * `ast.walk` over the whole tree would wrongly catch the two places in
        this repository that are already correct: `resources/lib/addon.py`
        imports `xbmc`, `xbmcplugin` and `xbmcvfs` inside `_dialog_smoke`, and
        `resources/lib/vendor/clouddrive_common/ui/utils.py` imports Kodi
        modules inside some twenty methods and never at the top. Both are what
        CI-01 asks for. So the descent stops at `FunctionDef`,
        `AsyncFunctionDef` and `ClassDef`.

    A name counts as Kodi when its first dotted component starts with `xbmc`,
    which covers `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcvfs`, `xbmcaddon` and
    anything Kodi adds later without this gate needing an edit.
    """
    hits = []

    def scan(body):
        for node in body or ():
            # A function or a class body runs when it is called or when the
            # class is defined -- either way, not at import. This is the whole
            # distinction the gate rests on.
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0].startswith('xbmc'):
                        hits.append((rel, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if module.split('.')[0].startswith('xbmc'):
                    hits.append((rel, node.lineno, module))
            for field in ('body', 'orelse', 'finalbody'):
                scan(getattr(node, field, None))
            for handler in getattr(node, 'handlers', None) or ():
                scan(handler.body)

    scan(ast.parse(_read(rel), filename=rel).body)
    return hits


def test_only_the_kodi_adapter_imports_kodi_at_module_level():
    """CI-01: one directory may import Kodi at import time, plus two exemptions.

    The offender set is what the scan finds minus what sits under the adapter
    directory minus what the exemption mapping names. Subtraction is what makes
    "exempt" and "violation" mutually exclusive for a given path: a path in
    both is reported as exempt and is separately held to still be doing work by
    the test below, so there is no third state to specify.

    An empty `MODULE_LEVEL_KODI_EXEMPTIONS` would not make this pass for free --
    it would fail on the two vendored UI modules, which is the correct answer
    for that input. What makes the green run mean something is the floor: a
    sweep that visited no files at all would otherwise be indistinguishable
    from a sweep that visited every file and found nothing.

    Offenders come out in the order `python_sources()` yields them, which is git
    index order. Nothing depends on that order; it is recorded so a reader does
    not go looking for a sort that is not there.
    """
    adapter_dir = REPO / KODI_ADAPTER_DIR.rstrip('/')
    assert adapter_dir.is_dir(), (
        '%s is not a directory; CI-01 names it as the one place a module-level '
        'Kodi import is permitted, and a prefix that names nothing on disk '
        'would report the adapter itself as an offender' % KODI_ADAPTER_DIR)

    visited = 0
    offenders = []
    for rel in python_sources():
        visited += 1
        if rel.startswith(KODI_ADAPTER_DIR):
            continue
        if rel in MODULE_LEVEL_KODI_EXEMPTIONS:
            continue
        offenders.extend(module_level_kodi_imports(rel))

    assert not offenders, (
        'these modules import Kodi when they are read, not when they are '
        'called, so they cannot be imported on a host with no Kodi installed '
        'and cannot be tested without a stub library -- which is how the pure '
        'core stops being pure. Move the dependency into %s, or take the '
        'import inside the function that needs it:\n%s'
        % (KODI_ADAPTER_DIR, _report(offenders)))
    assert visited >= 20, (
        'only %d Python sources were visited; the tree is not in place, so '
        'this sweep would pass without having checked it' % visited)


def test_every_kodi_import_exemption_is_load_bearing():
    """Each exemption must name a real file that is currently doing work.

    The same three mechanisms the URL exemptions are held to in the sibling gate
    file, translated from strings to paths, plus a fourth that only a directory
    boundary needs.

    An exemption list has exactly one failure mode: it widens without anybody
    deciding to widen it. A row that has stopped applying to its file is
    indistinguishable from a row that applies -- both are just strings until
    somebody checks the tree -- and it sits there covering whatever is written
    next.
    """
    tracked = set(tracked_files())

    for rel, reason in sorted(MODULE_LEVEL_KODI_EXEMPTIONS.items()):
        # 1. What is exempt is a location, not a prefix. An entry shortened
        #    towards a directory -- 'resources/lib/vendor/', say -- would
        #    absorb any future vendored module that grows a module-level Kodi
        #    import, switching the gate off for a whole subtree while leaving
        #    it green.
        assert not rel.endswith('/'), (
            '%r is a directory prefix; only an exact file may be exempt, and a '
            'prefix would absorb every module later added under it' % (rel,))
        assert rel in tracked, (
            '%r is exempt but is not in the git index, so the exemption '
            'excludes nothing. Delete the row, or restore the file it names.'
            % (rel,))

        # 2. The exemption is still doing work, measured with the same scanner
        #    the gate uses rather than with a second copy that could disagree.
        assert module_level_kodi_imports(rel), (
            '%r is exempt from the module-level Kodi rule but no longer has a '
            'module-level Kodi import. The row is dead and must be deleted '
            'rather than left to cover whatever is written next.' % (rel,))

        # 3. The reason is present, so a row cannot be added without saying
        #    what pays for it.
        assert isinstance(reason, str) and reason.strip(), (
            '%r is exempt with no reason given; a row without a reason is an '
            'escape hatch, and this mapping is meant to be a stricter demand'
            % (rel,))

    # 4. The permitted directory is doing work too. Without this the boundary
    #    would still pass after somebody deleted the adapter, and CI-01 would
    #    be certifying an empty directory.
    adapter = [rel for rel in python_sources()
               if rel.startswith(KODI_ADAPTER_DIR)
               and module_level_kodi_imports(rel)]
    assert adapter, (
        'no module under %s imports Kodi at module level. Either the adapter '
        'has gone, in which case CI-01 is certifying an empty directory, or the '
        'Kodi dependency moved somewhere this gate is not looking.'
        % KODI_ADAPTER_DIR)
