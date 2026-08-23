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
"""The provider's failure vocabulary, turned into something a renderer can use.

A tenant that refuses this application does not say so in a field. It says so
in `error_description`: a paragraph written for a developer reading a browser
console, carrying formatted links, a trace identifier and a timestamp. On a
television at three metres that paragraph is indistinguishable from showing
nothing, so it is never rendered. The one part of it a person can use is the
code buried in the prose, and finding that code is what this module is for.

Three properties hold this module's shape, and each of them is load-bearing:

  * **It returns identifiers, not words.** `classify` hands back a short
    symbolic outcome plus the bare code. Which sentence that outcome renders
    as is the Kodi layer's decision, read out of the string catalogue. Putting
    the sentences here would duplicate them in two places, and two copies of a
    sentence drift.

  * **The unmapped path keeps the code.** An unrecognised refusal still reaches
    the screen as a bare code, because a code a person can read off a
    television and quote to a maintainer is worth more than a friendly sentence
    that hides it.

  * **The administrator family is flagged rather than described.** Some
    refusals no amount of retrying will clear. Marking them lets the renderer
    stop offering a retry that cannot succeed and offer the escape hatch --
    the expert-level custom application identifier -- instead. That flag is
    what makes AUTH-18 and AUTH-19 one feature rather than two.

Nothing here imports a Kodi module and nothing here opens a socket, so the
whole table is testable as data.

**AUTH-18 is verified only in part.** The tenant hosting this registration
permits the device authorization grant, so no blocking response can be produced
from it on demand. The table below is written defensively over the union of the
candidates ROADMAP.md criterion 1a names and the refusals PITFALLS.md Pitfall 4
tables; which of them a genuinely blocking tenant actually returns is recorded
as unverified rather than claimed (D-08).
"""

import collections
import re

# The prefix is fixed and upper case, and the digits are what identify the
# refusal. Matching case-insensitively would let ordinary prose that happens to
# contain the letters route a user somewhere arbitrary, so it does not.
#
# A pattern rather than a lookup on a key because there is no key: the provider
# ships no structured field carrying this value, only the paragraph.
CODE_PATTERN = re.compile(r'AADSTS\d+')

# ---------------------------------------------------------------------------
# Outcomes
#
# Short identifiers, deliberately. Each one is a distinct thing that went wrong
# and a distinct thing the person in front of the television can do about it;
# two refusals that share an outcome are two refusals the renderer cannot tell
# apart, so no two entries in the table below collapse into one.
# ---------------------------------------------------------------------------

#: No entry in the table matched. The code, if there was one, is carried
#: through on the result and belongs on screen.
UNMAPPED = 'unmapped'

#: The registration in use is not marked as a public client. After shipping,
#: this is reachable only by somebody who set their own application identifier
#: and left that switch off, so its message is aimed at that person. The
#: provider's own wording for this refusal asks for a confidential-client
#: parameter, which is misdirection: the device authorization grant does not
#: support a confidential client at all, and following that wording breaks the
#: flow permanently while publishing something that then has to be rotated.
#: docs/AZURE-REGISTRATION.md section 4 says so at length; nothing in this
#: module may say otherwise.
PUBLIC_CLIENT_FLOWS_OFF = 'public_client_flows_off'

#: The person signing in has not granted this application access yet. They can
#: clear it themselves on the phone.
CONSENT_REQUIRED = 'consent_required'

#: The grant needs an administrator's consent, which the person signing in
#: cannot give.
ADMIN_CONSENT_REQUIRED = 'admin_consent_required'

#: The account exists but is not assigned to this application in the tenant.
NOT_ASSIGNED_TO_APPLICATION = 'not_assigned_to_application'

#: A conditional access policy refuses token issuance for this sign-in.
BLOCKED_BY_CONDITIONAL_ACCESS = 'blocked_by_conditional_access'

#: The tenant's security defaults refuse it, which is the same wall arriving
#: from the other direction and is worth its own sentence, because the setting
#: an administrator has to look at is a different one.
BLOCKED_BY_SECURITY_DEFAULTS = 'blocked_by_security_defaults'

#: A second authentication factor is required and has not been satisfied.
#: Completed on the phone, by the person signing in.
MFA_REQUIRED = 'mfa_required'

#: A second factor has to be enrolled before it can be satisfied. A different
#: sentence, because the action is set one up rather than complete one.
MFA_ENROLMENT_REQUIRED = 'mfa_enrolment_required'

#: The account's password has expired.
PASSWORD_EXPIRED = 'password_expired'

#: The application is disabled in the tenant.
APPLICATION_DISABLED = 'application_disabled'

#: The application is not present in the tenant at all.
APPLICATION_NOT_IN_TENANT = 'application_not_in_tenant'

#: The device code offered at the token endpoint was refused. Verified live
#: during the spike: an unrecognised device code returns `invalid_grant` with
#: this code, not the `bad_verification_code` the reference documents.
DEVICE_CODE_REJECTED = 'device_code_rejected'

#: The device code expired before anybody entered it. The window is fifteen
#: minutes and a person who walks off to find their phone loses it, which makes
#: this the terminal refusal this flow will actually produce most often.
DEVICE_CODE_EXPIRED = 'device_code_expired'


#: (outcome, administrator must act) for every refusal this add-on recognises.
#:
#: The union of ROADMAP.md criterion 1a's candidates and PITFALLS.md Pitfall 4's
#: table, plus the device-code expiry code. `admin_must_act` is not a severity:
#: it is the single question "can the person holding the remote clear this
#: themselves?", and it is False for every refusal that is cleared on the phone.
FAILURES = {
    'AADSTS7000218':  (PUBLIC_CLIENT_FLOWS_OFF,       False),
    'AADSTS65001':    (CONSENT_REQUIRED,              False),
    'AADSTS90094':    (ADMIN_CONSENT_REQUIRED,        True),
    'AADSTS50105':    (NOT_ASSIGNED_TO_APPLICATION,   True),
    'AADSTS53003':    (BLOCKED_BY_CONDITIONAL_ACCESS, True),
    'AADSTS530035':   (BLOCKED_BY_SECURITY_DEFAULTS,  True),
    'AADSTS50076':    (MFA_REQUIRED,                  False),
    'AADSTS50079':    (MFA_ENROLMENT_REQUIRED,        False),
    'AADSTS50055':    (PASSWORD_EXPIRED,              False),
    'AADSTS7000112':  (APPLICATION_DISABLED,          True),
    'AADSTS500011':   (APPLICATION_NOT_IN_TENANT,     True),
    'AADSTS7000014':  (DEVICE_CODE_REJECTED,          False),
    'AADSTS70019':    (DEVICE_CODE_EXPIRED,           False),
}

#: The four candidates ROADMAP.md criterion 1a names, marked so the acceptance
#: record can say which of them was actually observed on a blocking tenant and
#: which remains theoretical. Nothing routes on this set; it exists to be read.
ROADMAP_CANDIDATES = frozenset({
    'AADSTS7000218',
    'AADSTS65001',
    'AADSTS50105',
    'AADSTS53003',
    'AADSTS7000014',
})


#: What `classify` returns.
#:
#: `outcome`        one of the identifiers above; the renderer's lookup key.
#: `code`           the bare code, or '' when the description carried none.
#:                  Belongs on screen whatever the outcome, and is the only
#:                  thing on screen when the outcome is UNMAPPED.
#: `admin_must_act` True when retrying cannot help and the renderer should
#:                  offer the escape hatch instead.
Failure = collections.namedtuple('Failure', 'outcome code admin_must_act')


def extract_code(error_description):
    """The failure code buried in a description paragraph, or ''.

    Returns the first match. A response that chains two codes leads with the
    one describing the refusal; the rest are context, and picking the first is
    what makes the routing deterministic.
    """
    if not error_description:
        return ''
    found = CODE_PATTERN.search(error_description)
    return found.group(0) if found else ''


def classify(error_description):
    """Route a failure description onto a `Failure`.

    Takes the description rather than the response's `error` value, because
    every refusal in the table arrives as the same one or two generic values
    and the code inside the description is the whole signal.

    Never raises. A missing description, a description with no code in it and a
    code nobody has documented all classify; there is no input for which the
    caller has to hold a second path.
    """
    code = extract_code(error_description)
    entry = FAILURES.get(code)
    if entry is None:
        return Failure(UNMAPPED, code, False)
    outcome, admin_must_act = entry
    return Failure(outcome, code, admin_must_act)


def classify_response(payload):
    """Route a whole token-endpoint error body onto a `Failure`.

    The description is the primary source, but the provider also returns an
    `error_codes` array of bare integers -- verified live during the spike,
    which observed `[70016]` on a pending poll and `[7000014]` on a rejected
    device code. When a body arrives with that array and no usable description,
    reading the array is the difference between naming the refusal and showing
    nothing, so it is the fallback rather than a second code path for the
    caller to remember.
    """
    if not isinstance(payload, dict):
        return classify(payload if isinstance(payload, str) else '')

    failure = classify(payload.get('error_description'))
    if failure.outcome != UNMAPPED or failure.code:
        return failure

    for number in payload.get('error_codes') or ():
        candidate = 'AADSTS%s' % (number,)
        if CODE_PATTERN.match(candidate):
            return classify(candidate)
    return failure
