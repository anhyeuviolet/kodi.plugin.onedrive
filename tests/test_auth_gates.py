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
"""Repository gates for the authentication phase.

Every static claim this phase makes, written down as a named assertion before any
of them is true. Most of these are red on the day they are written; that is the
point. A red assertion with a named owner is a commitment. A claim with no
assertion behind it is a hope.

Like tests/test_vendor_gates.py, nothing here imports a Kodi module and nothing
here walks the filesystem: the shared harness in tests/gatelib.py reads the git
index, so an untracked scratch file cannot change a verdict, and the one
exclusion set lives there rather than being restated here.

Two rules every sweep below obeys:

  * Report path and line, never a count. A count cannot be acted on.
  * Carry a non-vacuity guard. A sweep that passes because it looked at nothing
    certifies nothing, and the way a sweep comes to look at nothing is a moved
    file or a renamed package -- exactly the changes this phase makes.
"""

import ast
import re
import xml.etree.ElementTree as ET

from gatelib import REPO, python_sources, read, report, source_scan, tracked_files

# The package that holds the protocol, the store and the lock. It has no Kodi in
# it, which is what makes it testable at all.
AUTH_PACKAGE = 'resources/lib/auth/'

# The transport the whole add-on makes every outbound call through.
TRANSPORT = 'resources/lib/vendor/clouddrive_common/remote/request.py'

# The plugin's router: the function that turns a plugin:// address into a call.
ROUTER = 'resources/lib/vendor/clouddrive_common/ui/addon.py'

# The service entry point. Its import closure is what AUTH-17 constrains.
SERVICE = 'service.py'

# Where the device-code constants live.
DEVICE_CODE = 'resources/lib/auth/device_code.py'

SETTINGS = 'resources/settings.xml'


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _parse(rel):
    return ast.parse(read(rel), filename=rel)


def _modules_under(prefix):
    return [rel for rel in python_sources()
            if rel.startswith(prefix) and rel.endswith('.py')]


def _constant_str(node):
    """The string a node evaluates to, or None if it is not a constant.

    A whole-expression literal_eval first, so `'/me' + '/drives'` is read as the
    path it actually is rather than as two fragments.
    """
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None
    return value if isinstance(value, str) else None


def _leftmost_literal(node):
    """The literal prefix of a concatenation, e.g. '/drives/' in '/drives/'+id."""
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.left
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _func_name(node):
    """A dotted, readable name for whatever a Call is calling."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_func_name(node.func) + '()')
    return '.'.join(reversed(parts))


# ---------------------------------------------------------------------------
# The scope set (AUTH-04)
# ---------------------------------------------------------------------------

# Locked by decision, measured by the spike, and not a preference. Read from
# source rather than imported, so this gate has no import of the add-on at all.
LOCKED_SCOPES = ('https://graph.microsoft.com/Files.Read',
                 'offline_access', 'openid', 'profile')


def test_scope_string_exact():
    tree = _parse(DEVICE_CODE)
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    value = _constant_str(node.value)
                    if value is not None:
                        found[target.id] = value

    assert 'SCOPES' in found, (
        '%s declares no SCOPES string constant. The requested scope set is a '
        'locked decision and it has to be readable as a constant, not assembled '
        'at call time.' % DEVICE_CODE)

    requested = found['SCOPES'].split()
    assert tuple(requested) == LOCKED_SCOPES, (
        'the requested scope set is not the locked one.\n  found:  %r\n  locked: %r'
        % (requested, list(LOCKED_SCOPES)))

    # Membership on the split, never a substring test on the whole string, and
    # never equality against what the endpoint hands back. The *granted* scope
    # differs from this one in both membership and ordering between account
    # classes -- the spike measured two different strings -- so any future test
    # over a granted scope may only ever ask whether a permission is in the list.
    for scope in requested:
        assert not scope.endswith('.All'), (
            'the scope set contains a broad-read form (%s). Files.Read is '
            'per-item consent; the .All forms read the whole tenant and are a '
            'different consent screen and a different risk.' % scope)
        assert 'ReadWrite' not in scope and 'Write' not in scope, (
            'the scope set contains a write permission (%s). This add-on plays '
            'media; it has no reason to be able to change anything.' % scope)
        assert not scope.endswith('/.default'), (
            'the scope set contains an application-wide grant form (%s). '
            '.default asks for everything the registration has ever been '
            'granted, which is the opposite of asking for what is needed.'
            % scope)


# ---------------------------------------------------------------------------
# The forbidden lock primitives (AUTH-14)
# ---------------------------------------------------------------------------
#
# The plugin and the background service are sub-interpreters inside ONE
# operating-system process. That single fact rules out both of the primitives
# a reader would reach for first:
#
#   fcntl        - POSIX record locks are associated with the *process*. A
#                  second lock on a region the process already holds is merely
#                  converted, and closing ANY descriptor for the file releases
#                  all of the process's locks on it. So fcntl.lockf cannot
#                  exclude the plugin from the service; whichever finishes
#                  first silently drops the other's lock.
#   threading    - separate sub-interpreters hold separate lock objects, so a
#                  threading.Lock in one is invisible to the other.
#
# os.open(..., O_CREAT | O_EXCL) is a filesystem primitive and is indifferent to
# who is asking, which is why it is the only mechanism that works here.

def test_no_forbidden_lock_primitives():
    modules = _modules_under(AUTH_PACKAGE)
    assert modules, (
        'no module found under %s - the sweep would pass having read nothing. '
        'Either the package moved or it is not in the git index.' % AUTH_PACKAGE)

    hits = []
    for rel in modules:
        tree = _parse(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == 'fcntl' or alias.name.startswith('fcntl.'):
                        hits.append((rel, node.lineno, 'import %s' % alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'fcntl':
                    hits.append((rel, node.lineno, 'from fcntl import ...'))
                if node.module == 'threading':
                    for alias in node.names:
                        if alias.name in ('Lock', 'RLock'):
                            hits.append((rel, node.lineno,
                                         'from threading import %s' % alias.name))
            elif isinstance(node, ast.Call):
                name = _func_name(node.func)
                if name in ('threading.Lock', 'threading.RLock', 'Lock', 'RLock'):
                    hits.append((rel, node.lineno, '%s()' % name))

    assert not hits, (
        'a lock primitive that cannot exclude this add-on from itself is in use '
        'under %s. The plugin and the service are sub-interpreters in one '
        'process; only an O_EXCL file lock separates them:\n%s'
        % (AUTH_PACKAGE, report(hits)))


# ---------------------------------------------------------------------------
# The external sign-in broker (AUTH-23)
# ---------------------------------------------------------------------------
#
# Every literal that can only be there because a third-party server sits in the
# middle of sign-in. Each is named separately so a failure says which one, and
# so that narrowing this list later is a visible edit rather than a silent one.
BROKER_LITERALS = (
    # The setting that points at the broker.
    r'sign-in-server',
    # The accessor every call site reads it through.
    r'get_signin_server',
    # The host it has always pointed at, and the project name in front of it.
    r'herokuapp',
    r'drive-login',
    # The two addresses composed against it: the page the QR used to encode and
    # the endpoint the IP-change heuristic used to poll.
    r'/signin/',
    r'/pin/',
)

# The two documents that are *required* to describe the flow being removed:
# README.md carries the project's status and VENDORED.md is the modification
# record, and deleting the history from a modification record is the one thing a
# modification record must not do. Both are already excluded from the sweeps in
# gatelib; test_the_replaced_flow_is_named_in_the_two_excluded_documents is what
# pays for that, exactly as the runbook's exclusion is paid for in the vendor
# gate file.
OLD_FLOW_DOCS = ('README.md', 'VENDORED.md')


def test_no_broker_references():
    hits = []
    for pattern in BROKER_LITERALS:
        hits.extend(source_scan(re.compile(pattern)))

    assert not hits, (
        'the external sign-in broker survives in shipped source. It is not dead '
        'code: the host answered as recently as 2026-08-22 and the add-on makes '
        'a live call to it before anything else in sign-in. Every site here is '
        'either a call to a third party or configuration for one:\n%s'
        % report(sorted(set(hits))))


def test_the_replaced_flow_is_named_in_the_two_excluded_documents():
    for rel in OLD_FLOW_DOCS:
        assert rel in tracked_files(), '%s is missing from the index' % rel
        contents = read(rel)

        named = re.search(r'device[ -]code|device authorization grant',
                          contents, re.IGNORECASE)
        assert named, (
            '%s does not name the flow that replaced the broker. It is excluded '
            'from the broker sweep so that it may describe the old flow; the '
            'price of that exclusion is that it also has to say what the flow is '
            'now, or the exclusion is just a hole.' % rel)

        mentions_broker = any(re.search(p, contents) for p in BROKER_LITERALS)
        if mentions_broker:
            # Naming the broker is allowed here and only here, but a reader who
            # meets it must be able to tell "this is history" from "this is how
            # it works", in the same document, without leaving it.
            assert re.search(r'no longer|replaced|used to|previously|removed|'
                             r'inherited|until then|before', contents,
                             re.IGNORECASE), (
                '%s names the broker without marking it as past. This document '
                'is exempt from the sweep precisely so it can record what was '
                'removed; recording it as if it were current is worse than not '
                'recording it.' % rel)


# ---------------------------------------------------------------------------
# The custom application identifier setting (AUTH-19)
# ---------------------------------------------------------------------------
#
# A setting's level is declared by a <level> ELEMENT inside <setting>, and that
# element belongs to the versioned settings format. The pre-version format this
# add-on inherited has no level concept at all, which is the whole reason the
# schema conversion was pulled into this phase rather than left in the deferred
# one. Read the element, not an attribute.
EXPERT_LEVEL = '3'


def test_custom_client_id_setting():
    root = ET.parse(str(REPO / SETTINGS)).getroot()

    assert root.get('version') == '1', (
        'resources/settings.xml is not in the versioned schema (version=%r). '
        'The <level> element that declares Expert exists only there, so an '
        'expert-level setting is not expressible until the file is converted.'
        % (root.get('version'),))

    candidates = [s for s in root.iter('setting')
                  if 'client_id' in (s.get('id') or '')]
    assert len(candidates) == 1, (
        'expected exactly one setting whose id names a client identifier, '
        'found %d: %r. This is the escape hatch a user whose tenant blocks the '
        'built-in registration depends on; two of them means one of them is '
        'the one nobody reads.'
        % (len(candidates), [s.get('id') for s in candidates]))

    setting = candidates[0]

    level = setting.find('level')
    assert level is not None, (
        'the %s setting declares no <level>, so it sits at Basic beside the '
        'ordinary options. It is not an ordinary option: setting it wrongly '
        'breaks sign-in entirely.' % setting.get('id'))
    assert (level.text or '').strip() == EXPERT_LEVEL, (
        'the %s setting is declared at level %r, not Expert (%s)'
        % (setting.get('id'), (level.text or '').strip(), EXPERT_LEVEL))

    default = setting.find('default')
    assert default is not None, (
        'the %s setting declares no <default>. It must default to empty, which '
        'is the value that means "use the one built into the add-on".'
        % setting.get('id'))
    assert not (default.text or '').strip(), (
        'the %s setting defaults to %r. Anything but empty ships a second '
        'registration to every install.' % (setting.get('id'), default.text))


# ---------------------------------------------------------------------------
# The background service never prompts (AUTH-17)
# ---------------------------------------------------------------------------
#
# The service runs at Kodi start, with no user in front of it and possibly a
# film playing. It may refresh silently and it may raise a non-modal
# notification; it may never open something that waits for a person. The rule is
# unenforceable by review -- the offending line is three calls deep in a module
# nobody diffs -- and trivial to enforce statically.

# The two constructions that open nothing, and why each one does not:
#
#   DialogProgressBG - Kodi's background progress bar. It renders in the corner,
#                      it takes no input and it cannot block. The export service
#                      already uses it, and the research names a non-modal
#                      notification as the only user-facing surface the service
#                      is permitted at all.
#   Dialog           - xbmcgui.Dialog is a handle, not a window. Constructing it
#                      displays nothing; what waits for a person is the method
#                      called on it afterwards, and those are caught below by
#                      name. Flagging the construction would forbid the
#                      permitted notification along with the forbidden prompts.
OPENS_NOTHING = frozenset({'DialogProgressBG', 'Dialog'})

# Methods of xbmcgui.Dialog that wait for a person. `notification` is absent on
# purpose: it is a toast, it returns immediately, and it is permitted.
BLOCKING_DIALOG_METHODS = frozenset({
    'ok', 'yesno', 'yesnocustom', 'info', 'select', 'multiselect',
    'contextmenu', 'numeric', 'input', 'browse', 'browseSingle',
    'browseMultiple', 'textviewer', 'colorpicker',
})

# The module that DEFINES the dialog classes. It is exempt because a definition
# module inevitably names its own classes inside its own factory methods, and
# that is not the service deciding to open one -- the decision is made at the
# call site, and every call site in the closure is in scope. The exemption is
# guarded below: this file must actually be the definition module.
DIALOG_DEFINITIONS = 'resources/lib/vendor/clouddrive_common/ui/dialog.py'


def _own_import_closure(entry):
    """Every module in this repository reachable from `entry` by import."""
    tracked = set(tracked_files())
    seen = set()
    queue = [entry]
    while queue:
        rel = queue.pop()
        if rel in seen or rel not in tracked:
            continue
        seen.add(rel)
        for node in ast.walk(_parse(rel)):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.append(node.module)
                names.extend(node.module + '.' + a.name for a in node.names)
            elif isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            for name in names:
                if not name.startswith('resources.'):
                    continue
                dotted = name.replace('.', '/')
                queue.append(dotted + '.py')
                queue.append(dotted + '/__init__.py')
    return sorted(seen)


def test_service_never_opens_a_dialog():
    closure = _own_import_closure(SERVICE)
    assert SERVICE in closure and len(closure) > 1, (
        'the import closure of %s came out empty or trivial, so the sweep read '
        'nothing. A moved entry point is the usual cause.' % SERVICE)

    # The exemption has to keep earning itself.
    definitions = _parse(DIALOG_DEFINITIONS)
    defined = {n.name for n in ast.walk(definitions)
               if isinstance(n, ast.ClassDef)}
    assert any(name.endswith('Dialog') or name.startswith('Dialog')
               for name in defined), (
        '%s is exempt from this sweep because it is where the dialog classes '
        'are defined, and it no longer defines any. Remove the exemption.'
        % DIALOG_DEFINITIONS)

    hits = []
    for rel in closure:
        if rel == DIALOG_DEFINITIONS:
            continue
        for node in ast.walk(_parse(rel)):
            if not isinstance(node, ast.Call):
                continue
            name = _func_name(node.func)
            leaf = name.rsplit('.', 1)[-1]
            receiver = name.rsplit('.', 1)[0] if '.' in name else ''

            if leaf == 'doModal':
                hits.append((rel, node.lineno, '%s()' % name))
                continue

            # A blocking method called on anything that is a dialog, whether it
            # was built inline (xbmcgui.Dialog().yesno) or held on the instance
            # (self._dialog.browse).
            if leaf in BLOCKING_DIALOG_METHODS and 'dialog' in receiver.lower():
                hits.append((rel, node.lineno, '%s()' % name))
                continue

            constructs_dialog = (
                (leaf.endswith('Dialog') or leaf.startswith('Dialog'))
                and leaf not in OPENS_NOTHING
                and leaf[:1].isupper())
            if constructs_dialog:
                hits.append((rel, node.lineno, '%s()' % name))

    assert not hits, (
        'the background service reaches something that waits for a person. It '
        'runs at Kodi start with nobody in front of the television; it may '
        'refresh silently and raise a notification, and nothing else:\n%s'
        % report(hits))


# ---------------------------------------------------------------------------
# Plugin dispatch (T-03-12)
# ---------------------------------------------------------------------------
#
# A plugin:// address is not a trusted input. It can arrive from a favourite, a
# stored playlist entry, a keymap or another add-on entirely, and the add-on has
# no way to tell which. Looking a method up on `self` from a value that came out
# of that address is therefore an arbitrary method call from an untrusted
# string, restricted only by whichever names the class happens to carry.

def test_dispatch_uses_an_explicit_mapping():
    tree = _parse(ROUTER)

    routes = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == 'route']
    assert len(routes) == 1, (
        'expected exactly one route() in %s, found %d. The sweep below is '
        'anchored on it.' % (ROUTER, len(routes)))
    route = routes[0]

    dynamic = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _func_name(node.func) == 'getattr':
            attribute = node.args[1] if len(node.args) > 1 else None
            if attribute is None or _constant_str(attribute) is None:
                dynamic.append((ROUTER, node.lineno,
                                'getattr(...) on a value, not a literal'))

    assert not dynamic, (
        'the router looks a method up by dynamic attribute access. The name it '
        'looks up comes from the request, and a request address can be '
        'constructed by anything on the device:\n%s' % report(dynamic))

    # The other half: forbidding the dynamic lookup means nothing if what
    # replaced it is a mapping with nothing in it.
    referenced = {n.id for n in ast.walk(route) if isinstance(n, ast.Name)}
    mappings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            reachable = any(t in referenced for t in targets)
            inside_route = any(node is child for child in ast.walk(route))
            if not (reachable or inside_route):
                continue
            keys = [_constant_str(k) for k in node.value.keys if k is not None]
            if keys and all(k is not None for k in keys):
                mappings.append((node.lineno, targets, keys))

    assert mappings, (
        'no explicit action mapping is reachable from route() in %s. An action '
        'name from a request must be looked up in a list somebody wrote down, '
        'not resolved against whatever the class happens to define.' % ROUTER)
    assert any(m[2] for m in mappings), (
        'the action mapping reachable from route() is empty, which routes '
        'nothing and forbids nothing')


# The subclass. It rewrites three friendly action names onto internal ones
# before the mapping is consulted, and it owns the temporary dialog affordance,
# so the routable set is the union of the two files and not either alone.
SUBCLASS = 'resources/lib/addon.py'

# The method that returns the mapping, in whichever file defines one. Named
# rather than discovered, because a sweep that discovers its own subject stops
# checking anything the moment the subject is renamed.
ACTION_MAP_FUNCTION = '_action_map'

# The method that rewrites a friendly name onto an internal one. Its keys are
# reachable action names deliberately absent from the mapping: they are
# translated before the lookup happens, exactly as they were before it.
RENAME_FUNCTION = '_rename_action'

# The affordance the television acceptance pass reaches all three dialogs
# through. See the comment on test_the_dialog_affordance_stays_routable.
DIALOG_AFFORDANCE = '_dialog_smoke'

# How many distinct action names the sweep must find before its verdict means
# anything. The tree constructs well over a dozen; ten is low enough not to be a
# maintenance burden and high enough that a sweep reading one file, or none,
# fails loudly instead of certifying an empty set.
MINIMUM_CONSTRUCTED_ACTIONS = 10


def _action_map_entries(rel):
    """(key, attribute-name, lineno) for every entry of `rel`'s action map.

    Both shapes an entry can take: a pair inside a dict literal, and an
    assignment into the dict a subclass got back from its base. Reading only the
    first would let a whole file's worth of entries hide behind the second, and
    a sweep that can be stepped around by changing syntax is not a sweep.
    """
    entries = []
    for node in ast.walk(_parse(rel)):
        if not (isinstance(node, ast.FunctionDef)
                and node.name == ACTION_MAP_FUNCTION):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Dict):
                for key, value in zip(child.keys, child.values):
                    name = _constant_str(key) if key is not None else None
                    if name is None:
                        continue
                    attribute = (value.attr if isinstance(value, ast.Attribute)
                                 else None)
                    entries.append((name, attribute, child.lineno))
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    name = _constant_str(target.slice)
                    if name is None:
                        continue
                    attribute = (child.value.attr
                                 if isinstance(child.value, ast.Attribute)
                                 else None)
                    entries.append((name, attribute, child.lineno))
    return entries


def _routable_actions():
    """Every action name the router can reach: mapped, plus rewritten."""
    mapped = {}
    for rel in (ROUTER, SUBCLASS):
        for name, attribute, lineno in _action_map_entries(rel):
            mapped[name] = (rel, attribute, lineno)

    rewritten = set()
    for rel in (ROUTER, SUBCLASS):
        for node in ast.walk(_parse(rel)):
            if not (isinstance(node, ast.FunctionDef)
                    and node.name == RENAME_FUNCTION):
                continue
            for dictionary in ast.walk(node):
                if not isinstance(dictionary, ast.Dict):
                    continue
                for key in dictionary.keys:
                    name = _constant_str(key) if key is not None else None
                    if name is not None:
                        rewritten.add(name)
    return mapped, rewritten


def _constructed_actions():
    """Every action name this add-on puts into an address it builds itself.

    Two shapes in Python -- a dict literal carrying an 'action' key, and an
    assignment into an existing params dict -- plus the settings file, whose
    rows carry a whole plugin:// address in an attribute. Derived rather than
    listed, so adding a fourteenth context-menu entry cannot quietly add a
    fourteenth address that does nothing when it is pressed.
    """
    found = []
    for rel in python_sources():
        for node in ast.walk(_parse(rel)):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if key is not None and _constant_str(key) == 'action':
                        name = _constant_str(value)
                        if name:
                            found.append((rel, node.lineno, name))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    if _constant_str(target.slice) != 'action':
                        continue
                    name = _constant_str(node.value)
                    if name:
                        found.append((rel, node.lineno, name))

    contents = read(SETTINGS)
    for lineno, line in enumerate(contents.splitlines(), start=1):
        for match in re.finditer(r'[?&]action=([A-Za-z_][A-Za-z0-9_]*)', line):
            found.append((SETTINGS, lineno, match.group(1)))
    return found


def test_every_constructed_action_is_routable():
    """Derived, not recalled.

    The mapping replacing the dynamic lookup is only as good as its coverage: a
    name this add-on writes into one of its own addresses and then does not map
    is a row that silently does nothing, and the way that happens is somebody
    adding the address and forgetting the entry. So the expected set is swept
    out of the tree on every run rather than written down once.
    """
    constructed = _constructed_actions()
    distinct = set(name for _, _, name in constructed)
    assert len(distinct) >= MINIMUM_CONSTRUCTED_ACTIONS, (
        'the sweep found only %d distinct action names (%r). It reads dict '
        'literals, params assignments and %s; finding almost none means it '
        'stopped reading, not that the tree stopped building addresses.'
        % (len(distinct), sorted(distinct), SETTINGS))

    mapped, rewritten = _routable_actions()
    unroutable = [(rel, lineno, name) for rel, lineno, name in constructed
                  if name not in mapped and name not in rewritten]
    assert not unroutable, (
        'this add-on builds an address naming an action the router cannot '
        'reach. Every one of these is a row or a context-menu entry that does '
        'nothing when it is pressed:\n%s' % report(sorted(set(unroutable))))

    crossed = ['%s -> self.%s (%s:%d)' % (name, attribute, rel, lineno)
               for name, (rel, attribute, lineno) in sorted(mapped.items())
               if attribute != name]
    assert not crossed, (
        'an entry in the action mapping routes a name to a method with a '
        'different name. Aliasing belongs in %s, where it is one readable '
        'table; an alias hidden inside the mapping is how a mapping stops '
        'being the list somebody wrote down:\n%s'
        % (RENAME_FUNCTION, '\n'.join(crossed)))


def test_the_dialog_affordance_stays_routable():
    """The one entry that must not be tidied away before the acceptance pass.

    `_dialog_smoke` is a temporary debug affordance and it looks exactly like
    something to delete. It is also the only way anybody reaches all three
    dialogs: QRDialogProgress is constructed deep inside sign-in, and the two
    export dialogs need a store with a record already in it. The television
    acceptance pass repeats the phase-1 checklist through it, so dropping it
    from the mapping would not fail anything -- it would make that pass produce
    a green that meant nothing.

    It is scheduled for removal, or for a debug-only gate, before release. When
    that happens this assertion goes with it, in the same commit, deliberately.
    """
    mapped, _ = _routable_actions()
    assert DIALOG_AFFORDANCE in mapped, (
        '%r is not in the action mapping. It is the only route to all three '
        'dialogs, and the acceptance checklist reaches them through it.'
        % DIALOG_AFFORDANCE)


def test_every_mapped_action_names_a_method_that_exists():
    """A mapping is a written-down list, and a list can be written down wrong.

    Replacing dynamic attribute lookup moves the failure from "calls whatever
    the address named" to "calls nothing" -- an entry pointing at a method that
    was renamed or deleted raises AttributeError when the mapping is built,
    which is to say when the row is pressed and not before.
    """
    defined = set()
    for rel in (ROUTER, SUBCLASS):
        for node in ast.walk(_parse(rel)):
            if isinstance(node, ast.FunctionDef):
                defined.add(node.name)

    mapped, _ = _routable_actions()
    assert mapped, (
        'no action mapping was found in %s or %s, so this sweep certifies '
        'nothing' % (ROUTER, SUBCLASS))

    missing = ['%s (%s:%d)' % (name, rel, lineno)
               for name, (rel, attribute, lineno) in sorted(mapped.items())
               if (attribute or name) not in defined]
    assert not missing, (
        'the action mapping names a method that no longer exists in %s or %s:'
        '\n%s' % (ROUTER, SUBCLASS, '\n'.join(missing)))


# ---------------------------------------------------------------------------
# The account list: re-authorisation, and removal that takes the credential
# ---------------------------------------------------------------------------
#
# The root of this add-on is the account list (AUTH-22). Three things about it
# are asserted here rather than left to a reading, because all three are the
# kind of omission that looks like nothing in a diff:
#
#   * removal that deletes the record and leaves the token file. The account
#     disappears from the screen, so the removal looks complete, and the stale
#     credential is only found when a re-added account fails a refresh against
#     a token the user believes they just replaced (AUTH-20, T-03-43).
#   * re-authorisation that writes a second record instead of replacing a blob,
#     which leaves the list showing one account twice.
#   * the per-drive removal option outliving the branch that made it reachable.

def _function(rel, name):
    for node in ast.walk(_parse(rel)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_in(node):
    """(dotted name, lineno) for every call made inside `node`."""
    return [(_func_name(child.func), child.lineno)
            for child in ast.walk(node) if isinstance(child, ast.Call)]


def test_removing_an_account_deletes_its_stored_credential():
    removal = _function(ROUTER, '_remove_account')
    assert removal is not None, (
        '%s has no _remove_account; this sweep certifies nothing' % ROUTER)

    calls = _calls_in(removal)
    assert calls, '_remove_account calls nothing, so it removes nothing'

    through_store = [name for name, _ in calls
                     if name.split('.')[-1] == 'remove_account'
                     and name != 'remove_account'
                     and 'account_manager' not in name]
    assert through_store, (
        'removing an account does not go through the token store. The record '
        'is what the list reads, so deleting it alone makes the removal look '
        'complete; the credential stays on disk and the failure it causes -- a '
        're-added account refusing a refresh against a token the user believes '
        'they just replaced -- has no visible cause. Calls seen: %r'
        % ([name for name, _ in calls],))


def test_the_per_drive_removal_path_is_gone():
    """Unreachable by measurement, not by opinion.

    Drive resolution is one call to GET /me/drive, which returns the default
    drive and only that: GET /drives is 403 on both account classes and is not
    a v1.0 endpoint at all, and GET /me/drives is 403 accessDenied for personal
    accounts. So an account carries exactly one drive, the `len(drives) > 1`
    branch that offered per-drive removal can never be taken, and the option and
    its handler are unreachable rather than merely unused.

    This repository's previous piece of apparently-dead code was load-bearing
    and merely unexplained (D-04), which is why the reason is written down here
    and in the commit body rather than the code being called waste.
    """
    survivors = [(rel, lineno, line) for rel, lineno, line
                 in source_scan(re.compile(r'_remove_drive'))]
    assert not survivors, (
        'the per-drive removal option or its handler survives:\n%s'
        % report(survivors))


def test_reauthorisation_replaces_a_blob_without_a_second_record():
    handler = _function(ROUTER, '_reauthorise_account')
    assert handler is not None, (
        '%s has no _reauthorise_account. It is the whole delivery path for the '
        "background service's silent failure: the service records a marker and "
        'never prompts, the list shows it, and the user chooses to sign in '
        '(AUTH-17, AUTH-22).' % ROUTER)

    calls = _calls_in(handler)
    saves = [(name, lineno) for name, lineno in calls
             if name.split('.')[-1] == 'save_account']
    tokens = [(name, lineno) for name, lineno in calls
              if name.split('.')[-1] == 'save_tokens']

    assert len(tokens) == 1, (
        're-authorisation writes the token blob %d times; it must write it '
        'once, through the store seam that merges rather than overwrites'
        % len(tokens))
    assert len(saves) == 1, (
        're-authorisation saves the account record %d times. Once, keyed to the '
        'account that already exists -- a second write is how one account comes '
        'to occupy two rows.' % len(saves))

    last_write = max(lineno for _, lineno in saves + tokens)
    assert saves[0][1] == last_write, (
        'the account record is not the last thing re-authorisation writes. '
        'Assembling in memory and writing last is what makes a cancel leave '
        'nothing behind, structurally rather than by a chain of guards.')


def test_the_account_list_offers_re_authorisation():
    listing = _function(ROUTER, 'list_accounts')
    assert listing is not None, (
        '%s has no list_accounts; this sweep certifies nothing' % ROUTER)

    contents = read(ROUTER)
    source = ast.get_source_segment(contents, listing) or ''
    assert '_reauthorise_account' in source, (
        'list_accounts never names the re-authorise action, so no row can '
        'reach it (AUTH-22)')

    # The option specifically, not merely the name somewhere in the method.
    # Naming the action while building the stale row's default address, and not
    # putting it in the menu, would leave every healthy account with no way to
    # sign in again short of removing it -- and that is the shape the first
    # draft of this assertion missed.
    menu = [child for child in ast.walk(listing)
            if isinstance(child, ast.Call)
            and _func_name(child.func).endswith('context_options.append')]
    assert menu, (
        'list_accounts builds no per-row menu at all, so this sweep certifies '
        'nothing')
    offered = [child for child in menu
               if 'reauthorise' in (ast.get_source_segment(contents, child) or '')]
    assert offered, (
        'the per-row menu does not offer re-authorisation. An account whose '
        'credentials went stale then has no way back except removal and a '
        'fresh sign-in, and the background service has no way to reach a user '
        'at all (AUTH-17, AUTH-22). The %d menu entries built here are: %r'
        % (len(menu), [ast.get_source_segment(contents, m) for m in menu]))


# ---------------------------------------------------------------------------
# The token blob the sign-in flow hands on (the local half of it)
# ---------------------------------------------------------------------------
#
# A provider token response is not a token blob. It carries `expires_in` and no
# `date`, and `date` is stamped locally by store.merge_token_response --
# OAuth2._validate_access_tokens requires it, and OAuth2.prepare_request
# computes expiry from `date + expires_in - 600`. So a raw poll response handed
# to the vendored OAuth2 layer is rejected by the first request made with it.
#
# That is not a theoretical seam. It shipped, and on hardware it turned a
# sign-in that had actually SUCCEEDED into a Kodi dialog reading "Access tokens
# provided are not valid" -- because _acquire_tokens returned the poll payload
# untouched and _identify passed it straight to provider.get_account.
#
# The stamp cannot be bought by persisting earlier: _add_account and
# _reauthorise_account both assemble everything in memory and write in their
# last two statements, so a cancel anywhere above leaves no partial account
# behind (AUTH-07). merge_token_response is a pure function and writes nothing,
# which is why it is the instrument that fits.
#
# This asserts the property at the one place that owns it: whatever
# _acquire_tokens returns has been through the merge.

TOKEN_MERGE = 'merge_token_response'


def _returned_names(func):
    """Every bare name `func` returns, ignoring `return` and `return None`."""
    names = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            names.append(node.value.id)
    return names


def test_the_signin_flow_stamps_the_token_before_returning_it():
    acquire = _function(ROUTER, '_acquire_tokens')
    assert acquire is not None, (
        '%s has no _acquire_tokens; it is the only producer of a fresh token '
        'blob in the tree, so this sweep certifies nothing without it' % ROUTER)

    returned = _returned_names(acquire)
    assert returned, (
        '_acquire_tokens returns no name at all, so either it stopped '
        'producing a token blob or this sweep is reading the wrong function')

    contents = read(ROUTER)
    source = ast.get_source_segment(contents, acquire) or ''

    # Bound from the merge, not merely mentioned somewhere in the function.
    merged_names = set()
    for node in ast.walk(acquire):
        if not isinstance(node, ast.Assign):
            continue
        if not any(_func_name(call.func).split('.')[-1] == TOKEN_MERGE
                   for call in ast.walk(node.value)
                   if isinstance(call, ast.Call)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                merged_names.add(target.id)

    unstamped = [name for name in returned if name not in merged_names]
    assert not unstamped, (
        '_acquire_tokens returns %r without putting it through '
        'store.%s. The provider sends no `date`; `date` is stamped locally '
        'and it is one of the four fields OAuth2._validate_access_tokens '
        'requires. So the very first request made with that blob raises '
        '"Access tokens provided are not valid", and a sign-in that succeeded '
        'is reported to the user as a failure. Assignments seen to have gone '
        'through the merge: %r\n%s'
        % (unstamped, TOKEN_MERGE, sorted(merged_names), source))


def test_the_signin_flow_stamps_without_writing_anything():
    """AUTH-07, restated where the stamp lands.

    The cheap way to make the blob valid is to persist it as soon as it
    arrives, and that trades this defect for a worse one: a cancel between the
    token arriving and the account record being written would leave a
    credential on disk with no account to own it. So the merge is allowed here
    and a write is not.
    """
    acquire = _function(ROUTER, '_acquire_tokens')
    assert acquire is not None, '%s has no _acquire_tokens' % ROUTER

    calls = _calls_in(acquire)
    assert calls, '_acquire_tokens calls nothing, so this sweep certifies nothing'

    writing = [(ROUTER, lineno, name) for name, lineno in calls
               if name.split('.')[-1] in ('write', 'save_tokens',
                                          'save_account', 'save_drive',
                                          'persist_access_tokens')]
    assert not writing, (
        '_acquire_tokens writes. Everything from the token arriving to the '
        'account record being saved is assembled in memory precisely so that a '
        'cancel anywhere in it leaves nothing behind (AUTH-07), and a write '
        'here puts a credential on disk that no account record owns:\n%s'
        % report(writing))


# ---------------------------------------------------------------------------
# The failure table's outcomes and the sentences they render as (AUTH-18)
# ---------------------------------------------------------------------------
#
# resources/lib/auth/errors.py holds identifiers and a flag and no words at all,
# and resources/language/.../strings.po holds the words and no logic. That split
# is what makes the table testable without Kodi and renderable without a second
# copy of the copy -- and it is also a join with nothing holding the two ends
# together. The pairing is written down twice, once as a comment above the .po
# block and once as the renderer's map, and neither file names the other's
# contents. So an outcome added to the table renders as nothing at all, and the
# way that shows up is a person in front of a television being told the sign-in
# failed and nothing else.
#
# This is the assertion that holds the join.

ERRORS_MODULE = 'resources/lib/auth/errors.py'
EN_GB_STRINGS = 'resources/language/resource.language.en_gb/strings.po'

# The name the Kodi layer's outcome-to-string-id map is bound to.
FAILURE_STRINGS_MAP = '_FAILURE_STRINGS'

# The outcome that deliberately has no sentence of its own: it renders through
# the fallback that keeps the bare provider code on screen, because a code a
# person can read off a television and quote is worth more than a friendly
# sentence that hides it.
UNMAPPED_OUTCOME = 'unmapped'

# The table had thirteen codes and fourteen outcomes on the day it was written.
# Non-vacuity only -- the assertion below is over whatever is there now.
MINIMUM_OUTCOMES = 13


def _outcome_constants():
    """Every symbolic outcome errors.py defines, by constant name and value."""
    outcomes = {}
    for node in ast.walk(_parse(ERRORS_MODULE)):
        if not isinstance(node, ast.Assign):
            continue
        value = _constant_str(node.value)
        if value is None or not re.match(r'^[a-z][a-z0-9_]*$', value):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                outcomes[target.id] = value
    return outcomes


def _failure_string_map():
    """(constant name -> string id) for the renderer's outcome map."""
    entries = {}
    for node in ast.walk(_parse(ROUTER)):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if FAILURE_STRINGS_MAP not in names:
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if not isinstance(key, ast.Attribute):
                continue
            if not (isinstance(value, ast.Constant)
                    and isinstance(value.value, int)):
                continue
            entries[key.attr] = value.value
    return entries


def test_every_failure_outcome_renders_its_own_sentence():
    outcomes = _outcome_constants()
    assert len(outcomes) >= MINIMUM_OUTCOMES, (
        'only %d outcomes were found in %s, so this sweep certifies nothing: '
        '%r' % (len(outcomes), ERRORS_MODULE, sorted(outcomes)))

    rendered = _failure_string_map()
    assert rendered, (
        '%s defines no %s, so no provider refusal renders as anything but the '
        'generic sentence. The catalogue already holds one sentence per '
        'outcome; without this map they are words nobody shows (AUTH-18).'
        % (ROUTER, FAILURE_STRINGS_MAP))

    expected = set(name for name, value in outcomes.items()
                   if value != UNMAPPED_OUTCOME)
    unrendered = sorted(expected - set(rendered))
    assert not unrendered, (
        'these outcomes route to no sentence, so a person meeting one is told '
        'the sign-in failed and nothing else: %r' % (unrendered,))

    unknown = sorted(set(rendered) - set(outcomes))
    assert not unknown, (
        '%s renders outcomes %s does not define. Either the table was renamed '
        'or the map was written from memory: %r'
        % (FAILURE_STRINGS_MAP, ERRORS_MODULE, unknown))

    for name, value in outcomes.items():
        if value == UNMAPPED_OUTCOME:
            assert name not in rendered, (
                'the unmapped outcome has a sentence of its own in %s. It must '
                'render through the fallback that keeps the bare provider code '
                'on screen -- that code is the one thing a person can read off '
                'a television and quote.' % FAILURE_STRINGS_MAP)

    declared = set(int(i) for i in re.findall(r'msgctxt "#(\d+)"',
                                              read(EN_GB_STRINGS)))
    absent = sorted(i for i in rendered.values() if i not in declared)
    assert not absent, (
        'the renderer names string ids the English catalogue does not declare, '
        'so they resolve to nothing on screen: %r' % (absent,))

    duplicated = sorted(i for i in set(rendered.values())
                        if list(rendered.values()).count(i) > 1)
    assert not duplicated, (
        'two outcomes render as the same sentence: %r. The table proves its '
        'entries distinct; rendering them identically throws that away at the '
        'last step' % (duplicated,))


# ---------------------------------------------------------------------------
# Endpoints that cannot be answered under the locked scope set
# ---------------------------------------------------------------------------
#
# Measured, not predicted, except where noted:
#
#   GET /drives      403 on both account classes. It is not a v1.0 endpoint at
#                    all; the documented forms are /me/drives, /users/{id}/drives,
#                    /groups/{id}/drives and /sites/{id}/drives.
#   GET /me/drives   200 for work/school, 403 accessDenied for personal. The
#                    requirement that named it was corrected in place.
#   GET /me          the profile endpoint's least-privileged delegated
#                    permission is User.Read, which is not in the locked scope
#                    set, for personal accounts as well as work ones.
#
# The last one is why this sweep exists as its own assertion. GET /me is the
# FIRST call sign-in makes after acquiring a token, so leaving it in breaks
# sign-in outright while every other check in this file stays green -- and it is
# a near-miss away from /me/drives, which is why the match below is on the whole
# parsed path and not on a prefix.
UNANSWERABLE_PATHS = frozenset({'/drives', '/me/drives', '/me'})

# The methods the provider layer sends a request through.
REQUEST_METHODS = frozenset({'get', 'post', 'put', 'patch', 'delete', 'request'})


def _request_paths():
    """(path, rel, lineno, complete?) for every provider request in the tree."""
    found = []
    for rel in python_sources():
        for node in ast.walk(_parse(rel)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in REQUEST_METHODS:
                continue
            if not node.args:
                continue
            # `request(method, path, ...)` puts the path second.
            argument = node.args[1] if func.attr == 'request' and len(node.args) > 1 \
                else node.args[0]
            complete = _constant_str(argument)
            if complete is not None:
                found.append((complete, rel, node.lineno, True))
                continue
            prefix = _leftmost_literal(argument)
            if prefix is not None:
                found.append((prefix, rel, node.lineno, False))
    return found


def test_no_unanswerable_provider_endpoint():
    paths = _request_paths()
    assert paths, (
        'no provider request path was collected, so this sweep certifies '
        'nothing. An import error, a renamed request method or a moved provider '
        'is what makes a sweep look at nothing and pass.')

    hits = []
    for path, rel, lineno, complete in paths:
        if not complete:
            # A concatenated path is a per-item address such as
            # '/drives/' + driveid + '/items/' + id, which is a documented
            # endpoint and answers under this scope set. Only the collection
            # endpoints are written as whole literals, and those are what is
            # forbidden -- so the test is on the whole value, never a prefix.
            continue
        if path.rstrip('/') or path == '/':
            normalised = path.rstrip('/') or '/'
        else:
            normalised = path
        if normalised in UNANSWERABLE_PATHS:
            hits.append((rel, lineno, '%s -> %s' % (path, normalised)))

    assert not hits, (
        'a request is made to an endpoint the locked scope set cannot answer. '
        'Each of these returns 403 and no amount of retrying changes that:\n%s'
        % report(hits))


# ---------------------------------------------------------------------------
# Credential redaction in the transport report (T-03-13)
# ---------------------------------------------------------------------------
#
# Every outbound call builds a report string and hands it to the logger. A Kodi
# log is copied into forum posts and attached to issues as a matter of routine,
# so a credential that reaches it is a credential that has been published. The
# device-code flow puts five credential-shaped fields through this transport:
# the three tokens, plus the two codes that are worth a session to whoever reads
# them before the user finishes signing in.
REDACTED_FIELDS = ('access_token', 'refresh_token', 'id_token',
                   'device_code', 'user_code')

# Attributes that hold an unredacted body: the request payload the add-on sent
# and the response the endpoint returned.
RAW_BODY_ATTRIBUTES = frozenset({'response', 'response_text', 'data'})


def _redacting_sources(rel):
    """Source of everything in `rel` that is part of building a report."""
    tree = _parse(rel)
    contents = read(rel)
    chunks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and (
                'report' in node.name.lower() or 'redact' in node.name.lower()):
            chunks.append(ast.get_source_segment(contents, node) or '')
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (
                        'REPORT' in target.id or 'REDACT' in target.id):
                    chunks.append(ast.get_source_segment(contents, node) or '')
    return '\n'.join(chunks)


def _raw_body_in_report_hits():
    """(hits, visited) for every report string built from an unredacted body.

    `visited` is the non-vacuity count: how many report-building assignments the
    sweep actually looked at. Zero means the transport was renamed out from
    under it, not that the tree is clean.
    """
    hits = []
    visited = 0
    for rel in python_sources():
        contents = read(rel)
        for node in ast.walk(_parse(rel)):
            if isinstance(node, ast.AugAssign):
                targets, value = [node.target], node.value
            elif isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            else:
                continue

            names = []
            for target in targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
                elif isinstance(target, ast.Attribute):
                    names.append(target.attr)
            if not any('report' in n.lower() for n in names):
                continue
            visited += 1

            # The length of a body is not the body. Logging len(response_text)
            # says how much came back and discloses nothing, and a rule that
            # forbade it would be asking a redactor to hide an integer.
            measured = set()
            for call in ast.walk(value):
                if isinstance(call, ast.Call) and _func_name(call.func) == 'len':
                    for argument in call.args:
                        measured.update(id(sub) for sub in ast.walk(argument))

            raw = [n for n in ast.walk(value)
                   if isinstance(n, ast.Attribute)
                   and n.attr in RAW_BODY_ATTRIBUTES
                   and id(n) not in measured]
            if not raw:
                continue
            redacted = any(
                isinstance(n, ast.Call)
                and ('for_report' in _func_name(n.func)
                     or 'redact' in _func_name(n.func).lower())
                for n in ast.walk(value))
            if not redacted:
                hits.append((rel, node.lineno,
                             (ast.get_source_segment(contents, node) or '').strip()))
    return hits, visited


def test_transport_report_redacts_credential_fields():
    assert TRANSPORT in tracked_files(), (
        '%s is missing; the transport is where every outbound call is logged'
        % TRANSPORT)

    redacting = _redacting_sources(TRANSPORT)
    assert redacting.strip(), (
        '%s builds no report and redacts nothing, so either the transport moved '
        'or the logging did' % TRANSPORT)

    absent = [field for field in REDACTED_FIELDS if field not in redacting]
    assert not absent, (
        'the transport report builder does not name %r. A redactor that covers '
        'four of the five is a redactor that publishes the fifth, and the one '
        'left out is always the one nobody thought of.' % (absent,))

    # The second half: naming the fields buys nothing if a raw body is
    # concatenated into the report somewhere else in the tree.
    hits, visited = _raw_body_in_report_hits()
    assert visited, (
        'the sweep found no report-building assignment anywhere in shipped '
        'source, so it certifies nothing. The transport builds two of them; if '
        'it does not, it moved.')
    assert not hits, (
        'a raw request or response body is concatenated into a report that goes '
        'to the log. A successful token response IS the credential, and the log '
        'it lands in gets pasted into issues:\n%s' % report(hits))


# ---------------------------------------------------------------------------
# Credential redaction in what an exception says (the second delivery path)
# ---------------------------------------------------------------------------
#
# The sweep above covers reports: strings assigned to a name containing
# "report" and handed to the logger. That is one of the two ways a credential
# reaches a person, and the other one is worse, because it does not stop at the
# log.
#
# An exception message is rendered onto the television.
# CloudDriveAddon._handle_exception puts a UIException's root exception on line
# two of a Kodi dialog, and _identify wraps every failure of
# provider.get_account in a UIException. So the text an exception carries is a
# user-visible string by construction.
#
# OAuth2._validate_access_tokens built its message as
# 'Access tokens provided are not valid: ' + Utils.str(access_tokens), and on
# hardware that printed a live token blob on screen -- token_type, scope,
# expires_in, then the access token itself. The report sweep could not see it:
# it was a raise, not an assignment, and the value was a local name rather than
# one of the raw-body attributes.
#
# This is the same rule stated over raises. It does not replace the sweep above
# and it does not narrow it.

# Names that hold a credential, or a whole body or blob that contains one, in
# this tree. `body` is here because that is what a token response is called in
# resources/lib/auth/refresh.py, and a token response IS the credential.
CREDENTIAL_BEARING_NAMES = frozenset({
    'access_token', 'refresh_token', 'id_token', 'device_code', 'user_code',
    'access_tokens', 'tokens_info', 'token_response', 'blob', 'merged',
    'body', 'response', 'response_text', 'payload', 'data', 'text',
    'headers', 'request_headers', 'fields',
})

# The one exception class allowed to be handed such a name. It is not an
# exclusion in the usual sense -- it is paid for by
# test_the_exempt_exception_keeps_its_body_out_of_its_message below, which
# reads the class and asserts the body never reaches the message. Widening this
# set without a matching positive assertion is how this gate stops checking.
EXEMPT_EXCEPTIONS = frozenset({'TransportError'})


def _redacting_call(node):
    """True if `node` is a call that hands back a redacted value."""
    if not isinstance(node, ast.Call):
        return False
    name = _func_name(node.func)
    tail = name.split('.')[-1]
    # The naming convention the transport established: *_for_report returns a
    # value fit to print. `fingerprint` is refresh.py's eight-character token
    # digest, and `len` is a measurement rather than a disclosure.
    return (tail.endswith('_for_report') or 'redact' in name.lower()
            or tail in ('fingerprint', 'len'))


def _credentials_in_raises():
    """(hits, visited) for every raise that carries a credential-bearing name.

    `visited` is the non-vacuity count. A tree with no raises in it is a tree
    this sweep certifies nothing about.
    """
    hits = []
    visited = 0
    for rel in python_sources():
        contents = read(rel)
        for node in ast.walk(_parse(rel)):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            visited += 1

            if (isinstance(node.exc, ast.Call)
                    and _func_name(node.exc.func).split('.')[-1]
                    in EXEMPT_EXCEPTIONS):
                continue

            # Everything underneath a redacting call is already safe.
            covered = set()
            for child in ast.walk(node.exc):
                if _redacting_call(child):
                    covered.update(id(sub) for sub in ast.walk(child))

            carried = sorted({
                child.id for child in ast.walk(node.exc)
                if isinstance(child, ast.Name)
                and child.id in CREDENTIAL_BEARING_NAMES
                and id(child) not in covered})
            if carried:
                hits.append((rel, node.lineno, '%s -> %s' % (
                    carried,
                    ' '.join((ast.get_source_segment(contents, node)
                              or '').split())[:160])))
    return hits, visited


def test_no_exception_message_carries_a_credential():
    hits, visited = _credentials_in_raises()
    assert visited, (
        'the sweep found no raise anywhere in shipped source, so it certifies '
        'nothing. The tree raises well over a hundred times; a count of zero '
        'means the file list moved, not that the tree is clean.')
    assert not hits, (
        'an exception is constructed from a credential-bearing value without '
        'going through a redactor. An exception message is not log-only: '
        '_handle_exception renders it onto a Kodi dialog, and _identify wraps '
        'every get_account failure in a UIException that reaches one. This is '
        'the construct that printed a live access token on a television:\n%s'
        % report(hits))


def test_the_invalid_token_message_is_built_from_field_names():
    """The positive half, at the site the defect was found.

    A sweep can say the blob is no longer stringified. It cannot say the
    message is still worth reading, and a redaction that reduces a failure to
    "not valid" costs a maintainer the one fact they need: which of the four
    required fields was absent.
    """
    oauth2 = 'resources/lib/vendor/clouddrive_common/remote/oauth2.py'
    assert oauth2 in tracked_files(), '%s is missing' % oauth2

    validator = _function(oauth2, '_validate_access_tokens')
    assert validator is not None, (
        '%s has no _validate_access_tokens; this sweep certifies nothing'
        % oauth2)

    source = ast.get_source_segment(read(oauth2), validator) or ''
    assert 'Utils.str(access_tokens)' not in source, (
        'the validator stringifies the whole blob into its message again. That '
        'message is rendered onto a Kodi dialog: it printed a live access '
        'token on a television once already')
    assert 'missing' in source, (
        'the validator no longer names which required field was absent, so the '
        'message says only that something was wrong. `date` missing means a '
        'response never went through store.merge_token_response, and that is '
        'the whole diagnosis')


def test_the_exempt_exception_keeps_its_body_out_of_its_message():
    """What buys TransportError its place in EXEMPT_EXCEPTIONS.

    device_code.poll_once raises it as `TransportError(status, body)`, and by
    the sweep's rule `body` is credential-bearing. It is safe for a reason that
    is a property of the class rather than of the call site: the message is
    built from `status` alone and `body` is only ever bound to an attribute. If
    that stops being true the exemption stops being paid for, and this fails.
    """
    tree = _parse(DEVICE_CODE)
    cls = next((node for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                and node.name == 'TransportError'), None)
    assert cls is not None, (
        '%s has no TransportError, so its entry in EXEMPT_EXCEPTIONS buys '
        'nothing and should go' % DEVICE_CODE)

    init = next((node for node in cls.body
                 if isinstance(node, ast.FunctionDef)
                 and node.name == '__init__'), None)
    assert init is not None, 'TransportError has no __init__ to read'

    message_calls = [node for node in ast.walk(init)
                     if isinstance(node, ast.Call)
                     and _func_name(node.func).endswith('Exception.__init__')]
    assert message_calls, (
        'TransportError does not build a message through Exception.__init__, '
        'so this assertion cannot see what it says and the exemption is unpaid')

    for call in message_calls:
        carried = [child.id for child in ast.walk(ast.Tuple(elts=call.args,
                                                            ctx=ast.Load()))
                   if isinstance(child, ast.Name)
                   and child.id in CREDENTIAL_BEARING_NAMES]
        assert not carried, (
            'TransportError now formats %r into its own message. The sweep '
            'exempts every raise of it on the strength of that not happening, '
            'so either the formatting goes or the exemption does.' % (carried,))

    assigned = {target.attr
                for node in ast.walk(init) if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Attribute)}
    assert 'body' in assigned, (
        'TransportError no longer keeps the body as an attribute, so this '
        'assertion is reading a class that has changed shape')


# ---------------------------------------------------------------------------
# The refresh transport profile (the three-way coupling nothing else can see)
# ---------------------------------------------------------------------------
#
# resources/lib/auth/refresh.py pins a short retry profile -- two attempts, a
# five-second delay, no backoff -- and states its arithmetic in a comment:
# 2 * 30 + 5 = 65 seconds worst case, against a RefreshLock lifetime of 90. The
# lock's lifetime was chosen against that number and against nothing else.
#
# But the profile is only values. It is the Kodi layer that hands them to the
# transport's constructor, and the transport's own defaults (tries=4, delay=5,
# backoff=2) put the worst case at 155 seconds -- sixty-five seconds PAST the
# lifetime, at which point a second contender judges a live lock stale and
# breaks it while the first is still mid-exchange. That is the precise race the
# lock exists to prevent.
#
# Neither the refresh module's tests nor the lock's can see it: from their side
# the profile is correct, and the call site that ignores it lives in a file
# neither of them may import, because importing it imports Kodi. So the
# coupling is asserted here, statically, on the one construction that carries
# it -- otherwise it is a comment, and a comment is not a constraint.
PROVIDER = 'resources/lib/vendor/clouddrive_common/remote/provider.py'

# The startup keepalive builds a transport of its own, and it is the contender
# that is MOST likely to meet the lock rather than least: it runs at Kodi start,
# which is when the user opens the add-on. A profile pinned in the provider and
# forgotten here would be a 155-second refresh under a 90-second lock reached
# only from the background service, where nobody is watching it happen.
STARTUP_REFRESH = 'resources/lib/startup_refresh.py'

REFRESH_TRANSPORT_FILES = (PROVIDER, STARTUP_REFRESH)

# The names, not the numbers. Asserting tries=2 would stay green against a
# literal 2 that nobody revisited when refresh.py changed its arithmetic; the
# whole point is that the two move together, and only a reference moves
# together.
REFRESH_PROFILE_ARGUMENTS = {
    'tries': 'REQUEST_TRIES',
    'delay': 'REQUEST_DELAY_SECONDS',
    'backoff': 'REQUEST_BACKOFF',
}

# What "building the transport" looks like in this file: either the transport
# itself, or the factory that wraps it into the `post(url, fields)` port the
# pure package takes. Both are named, because a provider with one factory and
# three call sites is better code than a provider with three copies of the same
# closure, and a gate that only recognised the raw construction would be
# pressure towards the worse one.
TRANSPORT_BUILDERS = frozenset({'Request', '_post_port'})


def _refresh_transport_constructions(rel):
    """Every transport built inside a refresh path in `rel`.

    "Inside the refresh path" is decided by the enclosing function's name,
    because that is what a reader can check by eye. A construction moved out of
    a function whose name says refresh is one this sweep stops seeing -- which
    is what the non-vacuity guard below is for.
    """
    found = []
    for node in ast.walk(_parse(rel)):
        if not isinstance(node, ast.FunctionDef):
            continue
        if 'refresh' not in node.name.lower():
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and \
                    _func_name(call.func).split('.')[-1] in TRANSPORT_BUILDERS:
                found.append((node.name, call))
    return found


def test_refresh_transport_is_built_from_the_pinned_profile():
    missing = []
    for rel in REFRESH_TRANSPORT_FILES:
        assert rel in tracked_files(), (
            '%s is missing; it is one of the two places the refresh reaches '
            'the network' % rel)

        constructions = _refresh_transport_constructions(rel)
        assert constructions, (
            'no transport construction was found inside a refresh function in '
            '%s, so this sweep certifies nothing about it. Either that refresh '
            'no longer builds its own transport -- in which case it has '
            'silently inherited the 155-second default profile -- or the '
            'function was renamed out from under this assertion.' % rel)

        contents = read(rel)
        for function_name, call in constructions:
            supplied = {keyword.arg: keyword for keyword in call.keywords
                        if keyword.arg}
            for argument, constant in REFRESH_PROFILE_ARGUMENTS.items():
                keyword = supplied.get(argument)
                if keyword is None:
                    missing.append((rel, call.lineno,
                                    '%s(): no %s=, so the transport default '
                                    'applies' % (function_name, argument)))
                    continue
                source = (ast.get_source_segment(contents, keyword.value)
                          or '').strip()
                if constant not in source:
                    missing.append((rel, call.lineno,
                                    '%s(): %s=%s does not name %s'
                                    % (function_name, argument, source,
                                       constant)))

    assert not missing, (
        'the refresh transport is not built from the profile refresh.py pins. '
        'On the transport defaults the worst case is 155 seconds against a lock '
        'lifetime of 90, so a slow network lets a second contender break a LIVE '
        'lock:\n%s' % report(missing))


# ---------------------------------------------------------------------------
# The code font (AUTH-05)
# ---------------------------------------------------------------------------
#
# WHAT THESE FOUR GATES PROVE, AND WHAT THEY CANNOT.
#
# They prove the layout's INTENT and its geometry: that the code label names
# the largest entry of a recorded chain of fonts, that the chain really is
# ordered by size, that every font the dialog names is one the stock skin
# defines, and that each box is tall and wide enough to hold the glyphs of the
# font it names without clipping them.
#
# They cannot prove what appeared on a television, and nothing in this
# repository can. Kodi resolves a font name against the ACTIVE skin at render
# time and substitutes font13 in silence when it cannot -- no exception, no log
# line, no return value. A layout that satisfies every assertion below is
# byte-identical whether the name resolved at 120px or fell back to 30, so
# these gates cannot distinguish the requirement being met from the exact
# failure the requirement is about.
#
# That is why AUTH-05 forbids recording itself as met from the layout, and
# these gates do not discharge that prohibition. What they buy is falsifiable
# intent: after a person has read the code off a screen once, a later edit
# cannot quietly walk the font back down, shrink the box under the glyphs, or
# name a font the skin does not define, without one of them going red.

PIN_DIALOG = 'resources/skins/default/1080i/pin-dialog.xml'

# The code label, and the body block whose last line is the expiry countdown.
CODE_CONTROL = '1005'
BODY_CONTROL = '1002'

# The panel is the one control textured with the dialog background. Identified
# by its texture rather than by its size, so the gate does not restate a number
# it is meant to be checking.
PANEL_TEXTURE = 'dialog-bg.png'

# The chain the layout's header comment records, with the sizes read out of
# skin.estuary's xml/Font.xml on xbmc/xbmc's Omega (Kodi 21) branch. Measured,
# not recalled. Descending: the order to walk if a code is too big for the
# panel on a real device. The head of it is what AUTH-05's "largest font the
# skin offers" resolves to on the stock skin.
#
# Kodi's skin XML has no fallback operator, so this chain is not something the
# renderer will walk. It is a chain for a human, kept here so that "the layout
# names a large font" is an assertion rather than a claim.
CODE_FONT_CHAIN = (
    ('WeatherTemp', 120),
    ('font_clock', 70),
    ('font60', 60),
    ('font52_title', 52),
    ('font45', 45),
)

# Every font id Estuary defines, in both the Default and the Arial fontsets,
# transcribed in 03-RESEARCH.md from xbmc/addons/skin.estuary/xml/Font.xml.
ESTUARY_FONTS = frozenset({
    'font10', 'font12', 'font13', 'font14', 'font23_narrow', 'font25_narrow',
    'font27', 'font27_narrow', 'font32', 'font37', 'font45', 'font60',
    'font_clock', 'font_flag', 'font20_title', 'font25_title', 'font30_title',
    'font32_title', 'font36_title', 'font40_title', 'font45_title',
    'font52_title', 'font_MainMenu', 'WeatherTemp', 'Mono26',
})

# One uppercase alphanumeric costs about 0.59 of the nominal font size in this
# face -- from 03-06's measurement of roughly 320px for a nine-character code
# at font60. Used for mixed-case body text as well, where it OVER-estimates:
# lowercase is narrower, so a wrap count computed with it is a ceiling and the
# gate errs towards demanding a bigger box.
ADVANCE_EM = 0.59

# A rendered line occupies more vertical space than the nominal size. 1.2 is a
# floor for a single label's glyph box and 1.4 a floor for stacked lines in a
# textbox; both are conservative for the Noto face Estuary ships.
GLYPH_BOX_RATIO = 1.2
LINE_HEIGHT_RATIO = 1.4

# The longest user code the provider has been observed to issue is nine
# characters (03-RESEARCH.md, three spike runs).
LONGEST_CODE = 9

# The address the server actually returns, measured 2026-08-22 and recorded in
# 03-RESEARCH.md. It is not the one most documentation cites, and it is the
# longest single unwrappable token in the body block.
VERIFICATION_URI = 'https://login.microsoft.com/device'

# The catalogue ids the body block renders: the instruction, the sentence that
# stops a personal account abandoning halfway, and the countdown template.
BODY_STRING_IDS = (30037, 30041, 30038)


def _pin_dialog_root():
    assert PIN_DIALOG in tracked_files(), (
        '%s is missing; there is no sign-in layout to check and every '
        'assertion in this section would certify nothing' % PIN_DIALOG)
    return ET.parse(str(REPO / PIN_DIALOG)).getroot()


def _box(control):
    """(left, top, width, height) from a control's direct children."""
    values = []
    for tag in ('left', 'top', 'width', 'height'):
        node = control.find(tag)
        if node is None:
            values.append(None)
            continue
        try:
            values.append(int((node.text or '').strip()))
        except ValueError:
            values.append(None)
    return tuple(values)


def _font_of(control):
    node = control.find('font')
    return (node.text or '').strip() if node is not None else None


def _controls_by_id(root):
    return {control.get('id'): control for control in root.iter('control')
            if control.get('id')}


def _line_of(contents, needle):
    """1-based line of the first occurrence, or 0 when it is not there."""
    for lineno, line in enumerate(contents.splitlines(), start=1):
        if needle in line:
            return lineno
    return 0


def _line_of_control(contents, control_id):
    """1-based line where one control opens.

    Located by its id attribute rather than by one of its values, because
    <width>1150</width> is true of the panel and of the code label both, and a
    hit that points at the wrong control is worse than one that points nowhere.
    """
    return _line_of(contents, 'id="%s"' % control_id)


def _catalogue_string(string_id):
    """The msgid for one id, read out of the shipped en_gb catalogue."""
    match = re.search(r'msgctxt "#%d"\s*\nmsgid "([^"]*)"' % string_id,
                      read(EN_GB_STRINGS))
    return match.group(1) if match else None


def test_the_code_font_chain_is_ordered_by_measured_size():
    """The recorded chain is a chain: strictly descending, all real names.

    Proves the list the next gate compares against is trustworthy. Proves
    nothing about any screen -- a correctly ordered list of fonts that no skin
    resolves would pass this untouched.
    """
    assert len(CODE_FONT_CHAIN) >= 2, (
        'CODE_FONT_CHAIN has fewer than two entries, so "walk down it" names '
        'nothing and the gate below degenerates into comparing one string to '
        'itself')

    out_of_order = [
        (PIN_DIALOG, 0, '%s (%d) is not larger than %s (%d), so the chain is '
                        'not ordered by size and "the largest" does not mean '
                        'the head of it'
         % (name, size, next_name, next_size))
        for (name, size), (next_name, next_size)
        in zip(CODE_FONT_CHAIN, CODE_FONT_CHAIN[1:])
        if next_size >= size
    ]
    assert not out_of_order, (
        'the code font chain is not ordered by measured size:\n%s'
        % report(out_of_order))

    unknown = [(PIN_DIALOG, 0, '%s is not a font Estuary defines' % name)
               for name, _ in CODE_FONT_CHAIN if name not in ESTUARY_FONTS]
    assert not unknown, (
        'the code font chain names a font the stock skin does not define, so '
        'stepping down to it would substitute font13 in silence:\n%s'
        % report(unknown))


def test_the_code_label_names_the_head_of_the_code_font_chain():
    """The code is set in the largest font of the chain, not merely a large one.

    Proves the layout asks for the largest size the stock skin defines. It
    cannot prove the ACTIVE skin defines that name: WeatherTemp is
    special-purpose and is the entry of the chain most likely to be absent from
    a third-party skin, where Kodi drops to font13 without logging it.
    """
    root = _pin_dialog_root()
    contents = read(PIN_DIALOG)
    control = _controls_by_id(root).get(CODE_CONTROL)
    assert control is not None, (
        '%s: control %s is gone. That control IS the code; without it there '
        'is no font for AUTH-05 to be about'
        % (PIN_DIALOG, CODE_CONTROL))

    named = _font_of(control)
    largest = CODE_FONT_CHAIN[0][0]
    assert named == largest, (
        '%s:%d: control %s is set in %r. AUTH-05 asks for the largest font the '
        'skin offers and the chain records that as %r (%dpx). If %r was chosen '
        'deliberately -- because the largest clipped on a real device, or '
        'because a skin did not define it -- record what was seen in the '
        'header comment and move the head of CODE_FONT_CHAIN with it.'
        % (PIN_DIALOG, _line_of(contents, '<font>%s</font>' % named),
           CODE_CONTROL, named, largest, CODE_FONT_CHAIN[0][1], named))


def test_every_font_the_sign_in_dialog_names_is_one_estuary_defines():
    """No name in the layout falls back to font13 on the stock skin.

    Proves resolution against the STOCK skin only, and only against a
    transcribed list. It says nothing about whichever skin is running on the
    device, which is the skin that decides what a person actually sees.
    """
    root = _pin_dialog_root()
    contents = read(PIN_DIALOG)
    named = [(node.text or '').strip() for node in root.iter('font')]
    assert len(named) >= 4, (
        '%s names %d fonts. The layout has a heading, a code, a body block and '
        'two buttons, so a count this low means the sweep is reading a '
        'different file or a rewritten one, and it certifies nothing'
        % (PIN_DIALOG, len(named)))

    unknown = [(PIN_DIALOG, _line_of(contents, '<font>%s</font>' % name),
                '%s is not defined by Estuary; Kodi renders it as font13 '
                '(30px) and logs nothing' % name)
               for name in named if name not in ESTUARY_FONTS]
    assert not unknown, (
        'the sign-in dialog names a font the stock skin does not define. This '
        'is how the file shipped with font12_title on its body text and '
        'rendered at the fallback for the whole of its life:\n%s'
        % report(unknown))


def test_the_sign_in_boxes_can_hold_the_fonts_they_name():
    """Every box is large enough for its glyphs, and the panel holds them all.

    Proves the arithmetic: a 120px code cannot clip in a 152-high box, nine
    characters fit the width, the body block has room for the lines it will be
    given, and the whole dialog stays inside the 1080-line space. This is the
    half of "the code is legible" that IS checkable. The other half -- whether
    the glyphs that arrived in those boxes were 120px or 30px -- is not.
    """
    root = _pin_dialog_root()
    contents = read(PIN_DIALOG)
    controls = _controls_by_id(root)
    sizes = dict(CODE_FONT_CHAIN)
    sizes.update({'font37': 37, 'font30_title': 30, 'font25_title': 25,
                  'font27': 27, 'font32': 32})

    too_small = []

    # The code label.
    code = controls.get(CODE_CONTROL)
    assert code is not None, (
        '%s: control %s is gone' % (PIN_DIALOG, CODE_CONTROL))
    code_font = _font_of(code)
    assert code_font in sizes, (
        '%s: control %s names %r, whose size is not recorded here, so this '
        'gate cannot check the box around it. Add it to CODE_FONT_CHAIN or to '
        'the sizes map, with the value read out of Font.xml'
        % (PIN_DIALOG, CODE_CONTROL, code_font))
    _, _, code_width, code_height = _box(code)
    code_size = sizes[code_font]
    needed_height = int(code_size * GLYPH_BOX_RATIO)
    needed_width = int(LONGEST_CODE * code_size * ADVANCE_EM)
    code_line = _line_of_control(contents, CODE_CONTROL)
    if code_height is None or code_height < needed_height:
        too_small.append((PIN_DIALOG, code_line,
                          'control %s is %s high for a %dpx font; %d is the '
                          'floor. A clipped code is worse than a small one'
                          % (CODE_CONTROL, code_height, code_size,
                             needed_height)))
    if code_width is None or code_width < needed_width:
        too_small.append((PIN_DIALOG, code_line,
                          'control %s is %s wide; %d characters at %dpx need '
                          '%d and a code that overruns its label is truncated'
                          % (CODE_CONTROL, code_width, LONGEST_CODE,
                             code_size, needed_width)))

    # The body block, whose last line is the countdown. This is the assertion
    # that would have been red before the 03-14 fix: font27 in a 156-high box
    # could not hold the five wrapped lines it was given, and the line pushed
    # out of view was the countdown.
    body = controls.get(BODY_CONTROL)
    assert body is not None, (
        '%s: control %s is gone; the instruction, the address and the '
        'countdown have nowhere to render' % (PIN_DIALOG, BODY_CONTROL))
    body_font = _font_of(body)
    assert body_font in sizes, (
        '%s: control %s names %r, whose size is not recorded here'
        % (PIN_DIALOG, BODY_CONTROL, body_font))
    _, _, body_width, body_height = _box(body)
    body_size = sizes[body_font]
    per_line = max(1, int(body_width / (body_size * ADVANCE_EM)))

    rendered = []
    for string_id in BODY_STRING_IDS:
        text = _catalogue_string(string_id)
        assert text, (
            'string %d is not in %s, so the body block\'s height is being '
            'checked against text the add-on does not ship'
            % (string_id, EN_GB_STRINGS))
        # The countdown template renders with a clock substituted in.
        rendered.append(text.replace('%s', '00:00'))
    rendered.append(VERIFICATION_URI)

    lines = sum(max(1, -(-len(text) // per_line)) for text in rendered)
    needed_body = int(lines * body_size * LINE_HEIGHT_RATIO)
    if body_height is None or body_height < needed_body:
        too_small.append((PIN_DIALOG, _line_of_control(contents, BODY_CONTROL),
                          'control %s is %s high. At %dpx in a %s-wide box the '
                          'shipped text wraps to %d lines and needs %d. The '
                          'line that goes over the edge is the last one, which '
                          'is the countdown'
                          % (BODY_CONTROL, body_height, body_size, body_width,
                             lines, needed_body)))

    assert not too_small, (
        'a control in the sign-in dialog is smaller than the text it is given:'
        '\n%s' % report(too_small))

    # Everything with an id lives inside the panel, and the panel lives inside
    # the coordinate space. The full-screen dimmer has no id and is meant to
    # overhang, which is why the sweep is over id'd controls.
    panel = None
    for control in root.iter('control'):
        if any(PANEL_TEXTURE in (node.text or '')
               for node in control.iter('texture')):
            panel = control
            break
    assert panel is not None, (
        '%s: no control is textured with %s, so the panel cannot be located '
        'and nothing below is being bounded by anything'
        % (PIN_DIALOG, PANEL_TEXTURE))
    _, _, panel_width, panel_height = _box(panel)

    origin = root.find('coordinates')
    assert origin is not None, (
        '%s: the window declares no <coordinates>' % PIN_DIALOG)
    left = int((origin.find('left').text or '0').strip())
    top = int((origin.find('top').text or '0').strip())

    origin_line = _line_of(contents, '<coordinates>')
    outside = []
    if left < 0 or left + panel_width > 1920:
        outside.append((PIN_DIALOG, origin_line,
                        'the panel spans %d..%d horizontally, outside the '
                        '1920-wide space' % (left, left + panel_width)))
    if top < 0 or top + panel_height > 1080:
        outside.append((PIN_DIALOG, origin_line,
                        'the panel spans %d..%d vertically, outside the '
                        '1080-line space' % (top, top + panel_height)))

    assert len(controls) >= 5, (
        '%s declares %d controls with ids; the dialog has a heading, a QR, a '
        'body block, two buttons and a code, so the sweep below is reading '
        'the wrong file' % (PIN_DIALOG, len(controls)))
    for control_id, control in sorted(controls.items()):
        box_left, box_top, box_width, box_height = _box(control)
        if None in (box_left, box_top, box_width, box_height):
            continue
        control_line = _line_of_control(contents, control_id)
        if box_left < 0 or box_left + box_width > panel_width:
            outside.append((PIN_DIALOG, control_line,
                            'control %s spans %d..%d horizontally, outside '
                            'the %d-wide panel'
                            % (control_id, box_left, box_left + box_width,
                               panel_width)))
        if box_top < 0 or box_top + box_height > panel_height:
            outside.append((PIN_DIALOG, control_line,
                            'control %s spans %d..%d vertically, outside the '
                            '%d-high panel'
                            % (control_id, box_top, box_top + box_height,
                               panel_height)))

    assert not outside, (
        'the sign-in dialog does not fit the space it is drawn in. A control '
        'past the panel edge is drawn over the background, and a panel past '
        'the screen edge is cropped by the compositor:\n%s' % report(outside))
# ---------------------------------------------------------------------------
# A redactor is not an instrument (the transferable lesson of 03-13)
# ---------------------------------------------------------------------------
#
# `refresh.fingerprint` returns the first eight characters of a token. It is
# sized for a log: a Kodi log is a file users paste into public forums verbatim,
# and eight characters answer "did this change" without carrying the credential.
#
# It answers that question for a HUMAN reading two lines. It does not answer it
# for CODE, and the difference is not academic. Every refresh token this
# registration issues begins `1.AXEAuM`, so three genuinely different tokens
# render as one identical string. A harness that decided rotation by putting
# fingerprints through a set therefore reported a confident FAIL on a run that
# had proved nothing -- and a PASS from that same code would have been just as
# worthless, which is the half that matters: the phase would have recorded its
# highest-consequence requirement as proven by a check that never worked.
#
# What is forbidden here is narrow on purpose. Comparing a fingerprint against a
# CONSTANT is how the function itself is tested and stays legal. What may not
# happen is deciding whether two *tokens* differ by comparing what the redactor
# made of them, in any of the shapes that decision is written in.

FINGERPRINT = 'fingerprint'


def _contains_fingerprint_call(node):
    """True if anywhere under `node` a call to fingerprint() is made."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            name = _func_name(inner.func)
            if name == FINGERPRINT or name.endswith('.' + FINGERPRINT):
                return True
    return False


def _is_fingerprint_call(node):
    """True if `node` is itself a call to fingerprint(), not merely containing one."""
    if not isinstance(node, ast.Call):
        return False
    name = _func_name(node.func)
    return name == FINGERPRINT or name.endswith('.' + FINGERPRINT)


def test_no_identity_decision_is_built_on_the_log_redactor():
    """Nothing may decide that two tokens differ by comparing their fingerprints.

    Three shapes, because the decision can be written three ways and banning one
    would leave a gate that reads as complete:

      1. a comparison with a fingerprint on two or more of its operands --
         `fingerprint(a) == fingerprint(b)`;
      2. a membership test whose left side is a fingerprint -- `fingerprint(a)
         in seen`, which is how the same decision is written when the collection
         is built up over a loop;
      3. a fingerprint handed to a set -- a literal `{...}`, `set(...)`,
         `frozenset(...)` or `.add(...)`. Deduplicating fingerprints has exactly
         one purpose, and counting the survivors is the shape that was actually
         written.

    Formatting is untouched: `'%s -> %s' % (fingerprint(a), fingerprint(b))` is
    a log line, which is the function's whole reason to exist, and it is what
    `refresh.py` does at both of its call sites.

    THE SUITE ITSELF IS SWEPT, not just shipped source. The code that got this
    wrong was a harness, not the add-on -- the add-on was never wrong -- so a
    gate that read only `resources/` would have been green while the defect sat
    in the file next door.
    """
    offenders = []

    sources = [rel for rel in tracked_files() if rel.endswith('.py')]
    assert sources, 'no python file in the index; the sweep would read nothing'

    for rel in sources:
        tree = ast.parse(read(rel), filename=rel)

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left] + list(node.comparators)
                carrying = [side for side in operands
                            if _contains_fingerprint_call(side)]
                if len(carrying) >= 2:
                    offenders.append((rel, node.lineno,
                                      'a comparison with a fingerprint on both '
                                      'sides'))
                elif (carrying
                      and any(isinstance(op, (ast.In, ast.NotIn))
                              for op in node.ops)
                      and _contains_fingerprint_call(node.left)):
                    offenders.append((rel, node.lineno,
                                      'a membership test on a fingerprint'))

            elif isinstance(node, ast.Set):
                if any(_contains_fingerprint_call(element)
                       for element in node.elts):
                    offenders.append((rel, node.lineno,
                                      'a fingerprint in a set literal'))

            elif isinstance(node, ast.Call):
                name = _func_name(node.func)
                if (name in ('set', 'frozenset') or name.endswith('.add')
                        or name == 'add'):
                    # CONTAINS, not IS. `set([fingerprint(a)])` hides the call
                    # one list-literal deep and is the same decision written
                    # with two more characters. That shape escaped the first
                    # version of this gate and was caught by driving it, not by
                    # reading it -- which is the standing lesson here: a gate
                    # nobody has made fail is a gate nobody has tested.
                    if any(_contains_fingerprint_call(argument)
                           for argument in node.args):
                        offenders.append((rel, node.lineno,
                                          'a fingerprint handed to %s()' % name))

    assert not offenders, (
        'an identity decision is being made on the output of a log redactor. '
        'fingerprint() keeps eight characters, and every refresh token this '
        'registration issues shares its first eight, so this compares different '
        'tokens as equal. Digest the whole value instead:\n%s' % report(offenders))
