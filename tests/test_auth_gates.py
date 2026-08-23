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
