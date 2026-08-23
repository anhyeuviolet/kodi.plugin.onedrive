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
"""The failure table: extraction, routing, and the two things it must never do.

A tenant that refuses this application says so in a paragraph written for a
developer reading a browser console. The only part of that paragraph a person
on a sofa can use is the code buried in it, so this module's whole job is to
find the code, route on it, and hand back something the Kodi layer can render
without ever putting the provider's prose on a television.

This file lives under `tests/`, which `tests/gatelib.py` excludes from the
shipped-source sweeps. That is what lets it quote the AADSTS7000218 response
verbatim -- credential parameter names and all -- so the extraction is tested
against the real thing rather than against a tidied paraphrase. The module
under test is shipped source and is asserted below to contain neither name.
"""

import re

from gatelib import read

from resources.lib.auth import errors


# The AADSTS7000218 response, as the runbook records it. Quoted rather than
# paraphrased because the shape of the paragraph -- code, colon, prose, quoted
# parameter names, then three identifier lines -- is exactly what the extraction
# has to survive.
REAL_7000218 = (
    "AADSTS7000218: The request body must contain the following parameter: "
    "'client_assertion' or 'client_secret'.\r\n"
    "Trace ID: 8c4b9d61-1f0e-4a77-b3c2-2f9a0d5e7c00\r\n"
    "Correlation ID: 4d1e3f72-90aa-4c85-a0f1-6b7c8d9e0a11\r\n"
    "Timestamp: 2026-08-23 04:11:02Z"
)

# A conditional-access refusal, with the markdown link Microsoft embeds. The
# link is the second reason this paragraph can never reach a screen.
REAL_53003 = (
    "AADSTS53003: Access has been blocked by Conditional Access policies. "
    "The access policy does not allow token issuance. "
    "See [Conditional Access](https://learn.microsoft.com/entra/identity/"
    "conditional-access/overview) for details.\r\n"
    "Trace ID: 0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9\r\n"
    "Timestamp: 2026-08-23 04:12:44Z"
)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def test_the_code_is_extracted_from_a_realistic_description_paragraph():
    assert errors.extract_code(REAL_7000218) == 'AADSTS7000218'
    assert errors.extract_code(REAL_53003) == 'AADSTS53003'


def test_extraction_returns_the_first_code_when_a_paragraph_names_two():
    # Microsoft chains codes in a few responses. First wins, deterministically,
    # because the first is the one that describes the refusal; the rest are
    # context.
    both = ('AADSTS50076: Due to a configuration change made by your '
            'administrator, you must use multi-factor authentication. '
            'AADSTS50079: User is required to enrol.')
    assert errors.extract_code(both) == 'AADSTS50076'


def test_a_lowercase_prefix_is_not_a_code():
    # The prefix is fixed and upper case. Matching case-insensitively would let
    # a sentence of ordinary prose that happens to contain the letters route a
    # user somewhere arbitrary.
    assert errors.extract_code('aadsts65001: not a code') == ''


def test_a_prefix_with_no_digits_is_not_a_code():
    assert errors.extract_code('AADSTS: the request was refused') == ''


def test_an_absent_description_does_not_raise():
    for empty in ('', None):
        assert errors.extract_code(empty) == ''


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

# The union of the four candidates ROADMAP.md criterion 1a names and the nine
# PITFALLS.md Pitfall 4 tables, plus the device-code expiry code. Written out
# here rather than derived from the module, so that dropping an entry from the
# table fails this file instead of silently agreeing with it.
EXPECTED_CODES = {
    'AADSTS7000218',    # 'Allow public client flows' is still off
    'AADSTS65001',      # the user has not consented
    'AADSTS90094',      # an administrator has to consent
    'AADSTS50105',      # the account is not assigned to the application
    'AADSTS53003',      # conditional access blocks it
    'AADSTS530035',     # security defaults block it
    'AADSTS50076',      # a second factor is required
    'AADSTS50079',      # a second factor has to be enrolled first
    'AADSTS50055',      # the password has expired
    'AADSTS7000112',    # the application is disabled in the tenant
    'AADSTS500011',     # the application is not present in the tenant
    'AADSTS7000014',    # the device code was rejected
    'AADSTS70019',      # the device code expired before it was used
}


def test_the_table_covers_the_union_of_the_roadmap_and_the_pitfall_record():
    assert set(errors.FAILURES) == EXPECTED_CODES


def test_the_table_has_thirteen_entries():
    assert len(errors.FAILURES) == 13


def test_every_mapped_code_routes_to_its_own_distinct_outcome():
    outcomes = [errors.classify(code).outcome for code in errors.FAILURES]
    duplicated = sorted({o for o in outcomes if outcomes.count(o) > 1})
    assert not duplicated, (
        'these outcomes are reached by more than one code, so the sentence the '
        'renderer picks cannot tell the two failures apart: %r' % (duplicated,))
    assert len(set(outcomes)) == len(errors.FAILURES)


def test_routing_reads_the_description_not_the_oauth_error_value():
    # Every one of these arrives as `invalid_grant` or `invalid_client`. The
    # OAuth error value is the same for all of them and carries no information;
    # the code inside the description is the whole signal.
    assert errors.classify(REAL_53003).outcome == errors.BLOCKED_BY_CONDITIONAL_ACCESS
    assert errors.classify(REAL_7000218).outcome == errors.PUBLIC_CLIENT_FLOWS_OFF


def test_a_mapped_outcome_carries_its_own_code_back():
    assert errors.classify(REAL_7000218).code == 'AADSTS7000218'


# ---------------------------------------------------------------------------
# The unmapped fallthrough
# ---------------------------------------------------------------------------

def test_an_unmapped_code_yields_the_unmapped_outcome():
    unknown = ('AADSTS999999: Something nobody has documented happened. '
               'Trace ID: 1234')
    assert errors.classify(unknown).outcome == errors.UNMAPPED


def test_the_unmapped_outcome_preserves_the_bare_code():
    # The point of the whole fallthrough. A user with no log, no console and no
    # keyboard can still read six digits off a television and quote them.
    unknown = 'AADSTS999999: Something nobody has documented happened.'
    assert errors.classify(unknown).code == 'AADSTS999999'


def test_a_description_carrying_no_code_yields_the_unmapped_outcome_without_raising():
    failure = errors.classify('The service is unavailable. Please try later.')
    assert failure.outcome == errors.UNMAPPED
    assert failure.code == ''


def test_an_absent_description_classifies_rather_than_raising():
    for empty in ('', None):
        failure = errors.classify(empty)
        assert failure.outcome == errors.UNMAPPED
        assert failure.code == ''


def test_an_unmapped_failure_never_claims_an_administrator_must_act():
    # Marking an unknown failure as administrator-must-act would suppress the
    # retry for a failure that may well be transient.
    assert errors.classify('AADSTS999999: unknown').admin_must_act is False


# ---------------------------------------------------------------------------
# The administrator family
# ---------------------------------------------------------------------------

# The refusals no amount of retrying can clear, and the only ones for which the
# renderer should replace "try again" with the escape hatch.
ADMIN_CODES = {
    'AADSTS90094', 'AADSTS50105', 'AADSTS53003',
    'AADSTS530035', 'AADSTS7000112', 'AADSTS500011',
}


def test_the_administrator_family_is_marked_and_nothing_else_is():
    marked = {code for code in errors.FAILURES
              if errors.classify(code).admin_must_act}
    assert marked == ADMIN_CODES


def test_a_failure_the_person_can_clear_themselves_is_not_marked():
    # Consent, a second factor and an expired password are all cleared on the
    # phone by the person signing in. Telling them to fetch an administrator
    # sends them away from the one action that works.
    for code in ('AADSTS65001', 'AADSTS50076', 'AADSTS50079', 'AADSTS50055'):
        assert errors.classify(code).admin_must_act is False, code


def test_the_public_client_code_is_not_an_administrator_outcome():
    # After shipping, AADSTS7000218 can only be reached by somebody who set
    # their own application identifier and left the public-client switch off.
    # Pointing that person at the custom-identifier setting they have already
    # used, or at an administrator, is the one piece of advice that cannot help.
    assert errors.classify(REAL_7000218).admin_must_act is False


def test_the_administrator_flag_is_a_bool_not_a_truthy_value():
    for code in errors.FAILURES:
        assert isinstance(errors.classify(code).admin_must_act, bool), code


# ---------------------------------------------------------------------------
# The roadmap's four candidates
# ---------------------------------------------------------------------------

def test_the_roadmap_candidates_are_named_and_all_mapped():
    # ROADMAP.md criterion 1a names these four candidates and instructs that
    # AUTH-18 be recorded unverified against a genuinely blocking tenant. They
    # are marked here so the acceptance record can say which were observed.
    assert errors.ROADMAP_CANDIDATES == frozenset({
        'AADSTS7000218', 'AADSTS65001', 'AADSTS50105',
        'AADSTS53003', 'AADSTS7000014',
    })
    assert errors.ROADMAP_CANDIDATES <= set(errors.FAILURES)


# ---------------------------------------------------------------------------
# What the module must not be
# ---------------------------------------------------------------------------

SOURCE = 'resources/lib/auth/errors.py'


def _source():
    return read(SOURCE)


def test_no_outcome_could_be_read_as_advice_to_add_a_credential():
    # T-03-22. AADSTS7000218 reads as "you forgot the secret", and a table that
    # repeats that reading -- even in a comment a maintainer skims -- is how a
    # credential ends up in a GPL source tree. The runbook says the same thing
    # in bold; this asserts the table never says the opposite.
    forbidden = re.compile(r'client_secret|client_assertion|add a secret|'
                           r'certificate', re.IGNORECASE)
    hits = [(n, line) for n, line in enumerate(_source().splitlines(), 1)
            if forbidden.search(line)]
    assert not hits, (
        'the failure table names a credential parameter: %r' % (hits,))


def test_the_table_holds_no_sentence_and_no_string_id():
    # The split that lets the table be tested without Kodi and rendered without
    # duplicating it: outcomes are identifiers, words live in the catalogue, and
    # the choice of which string an outcome renders as belongs to the Kodi layer.
    for code, entry in errors.FAILURES.items():
        outcome = errors.classify(code).outcome
        assert re.match(r'^[a-z][a-z0-9_]*$', outcome), (
            '%s routes to %r, which is prose rather than an identifier'
            % (code, outcome))
        assert ' ' not in outcome, code

    ids = re.findall(r'\b3[0-9]{4}\b', _source())
    assert not ids, (
        'the table names localised string ids %r. Choosing the string is the '
        'Kodi layer\'s job; naming ids here is the duplication that drifts'
        % (ids,))


def test_nothing_in_the_module_imports_kodi():
    assert not re.search(r'^\s*(import|from)\s+xbmc', _source(), re.MULTILINE)


def test_classify_returns_the_same_shape_for_every_input():
    for description in (None, '', 'no code here', REAL_7000218,
                        'AADSTS999999: unknown'):
        failure = errors.classify(description)
        assert failure._fields == ('outcome', 'code', 'admin_must_act')
