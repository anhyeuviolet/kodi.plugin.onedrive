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
"""The recorded-Graph harness's own contracts, and the rule that keeps the
fixture set honest about which kind of drive each response came from.

Two things live here because they hold each other up.

**The harness.** Every Layer 1 test in this phase reads its input through
`load_graph_envelope` and drives its code through `FakeGraph`. `FakeGraph` is a
deliberate copy of `FakeTokenEndpoint`, which has four load-bearing properties:
the script is positional and consumed in order, a call is recorded *before* it is
answered, running off the end fails loudly instead of repeating the last answer,
and what was requested is readable afterwards. A copy nobody asserts is a copy
that drifts, so all four are asserted here rather than assumed from the original.

**The labelling.** An unlabelled fixture set silently starts reading as "both".
The two drive classes are not interchangeable: Microsoft's reserved-character
list forbids `#` and `%` in a name on a Business drive outright, so those two
characters are Personal-drive cases by construction, and a suite green against
Business fixtures proves nothing about Personal ones. CI-03 asks for the
labelling and SETUP-05 paid for two accounts to make it possible; a convention
that both are represented is worth nothing once somebody deletes a directory to
make a test pass. So the rule is a gate.

The gate reads the git index through `gatelib.tracked_files()` and never walks
the filesystem, so an untracked scratch capture sitting in the working tree
cannot influence the verdict, and it carries a non-vacuity guard, because a sweep
that passes because it found nothing certifies nothing.
"""

from pathlib import PurePosixPath

import pytest

from conftest import (
    DRIVE_CLASSES,
    GraphTransportError,
    load_graph_envelope,
)
from gatelib import report, tracked_files

# Everything the fixture set is allowed to hold, and the one file that is
# allowed to sit outside a drive-class directory because it describes the set
# rather than belonging to either half of it.
GRAPH_FIXTURE_PREFIX = 'tests/fixtures/graph/'
UNLABELLED_ALLOWED = frozenset({'README.md'})

# The scan must see at least this many fixtures. The set holds twenty-seven
# today; a floor of twenty leaves room for one to be retired without re-pinning
# and still fails outright if the prefix stops matching anything, which is how a
# gate quietly starts certifying an empty list.
MINIMUM_FIXTURES = 20


def _graph_fixture_paths():
    """Every tracked path under the fixture root, sorted.

    Sorted so the order the two drive classes are visited in is stable and a
    failure report reads the same way twice. Nothing in this file depends on the
    order within a class.
    """
    return sorted(rel for rel in tracked_files()
                  if rel.startswith(GRAPH_FIXTURE_PREFIX))


# ---------------------------------------------------------------------------
# The loader
# ---------------------------------------------------------------------------

def test_the_loader_refuses_a_drive_class_it_does_not_know():
    """The drive class is required and validated, not defaulted.

    A default is what would let a Business-only run read as coverage of both,
    which is the exact substitution the labelling rule exists to prevent.
    """
    with pytest.raises(AssertionError) as caught:
        load_graph_envelope('sharepoint', 'root_children')

    message = str(caught.value)
    for known in DRIVE_CLASSES:
        assert known in message, (
            'the rejection message %r does not name %r. A caller who guessed '
            'the wrong drive class needs to be told which ones exist, in the '
            'message they are already reading' % (message, known))


def test_the_loader_returns_the_whole_envelope():
    """Two envelope shapes exist, so the loader may not reach for `body`.

    `children_by_path_unencoded` is the recorded BROWSE-05 failure: no status
    and no body, because `http.client` raised before a request left the machine.
    A loader that indexed `body` unconditionally could not express it at all.
    """
    envelope = load_graph_envelope('business', 'children_by_path_unencoded')

    assert 'body' not in envelope, (
        'the bodiless envelope came back carrying a body: %r' % (envelope,))
    assert envelope['status'] is None, (
        'the recorded status is %r, not None. This fixture records a request '
        'that was never sent, so there is no status to have'
        % (envelope['status'],))
    assert envelope['transport_error'] == 'InvalidURL', (
        'the recorded transport error is %r; the failure BROWSE-05 names is '
        'InvalidURL, raised by http.client before the socket is opened'
        % (envelope['transport_error'],))


def test_asking_a_bodiless_envelope_for_a_body_names_the_file(graph_body):
    """A KeyError here would say `body` and nothing else.

    The caller's actual mistake is having asked a transport-failure fixture for
    a page of results, and the only thing that makes that legible is the file's
    own name.
    """
    with pytest.raises(AssertionError) as caught:
        graph_body('business', 'children_by_path_unencoded')

    assert 'children_by_path_unencoded' in str(caught.value), (
        'the failure message %r does not name the fixture that has no body'
        % (str(caught.value),))


def test_a_body_is_the_recorded_page_itself(graph_body):
    """The count is pinned because the page size is what the pager tests read.

    A fixture silently truncated to a handful of entries would leave every
    paging assertion built on it passing against a page that no longer resembles
    the one the drive returned.
    """
    body = graph_body('business', 'root_children')

    assert len(body['value']) == 121, (
        'the recorded root listing holds %d entries, not the 121 that were '
        'captured' % (len(body['value']),))


# ---------------------------------------------------------------------------
# The scripted port
# ---------------------------------------------------------------------------

def test_a_call_is_recorded_before_it_is_answered(fake_graph):
    """Recorded first, answered second.

    The call that fails is the most interesting one there is -- it is the extra
    request nobody intended -- and a port that recorded after answering would
    lose exactly that one.
    """
    port = fake_graph()

    with pytest.raises(AssertionError):
        port('/drives/synthetic/root/children')

    assert port.paths == ['/drives/synthetic/root/children'], (
        'the call that ran off the end of the script is not on `calls`: %r. '
        'The request a test did not expect is the one worth seeing'
        % (port.paths,))


def test_running_off_the_end_of_the_script_fails_loudly(fake_graph):
    """Never repeat the last answer.

    A pager that fetches one page more than the test intended is a bug the
    harness must report, not absorb -- and absorbing it is precisely what
    re-serving the last page would do, since a repeated final page looks like a
    listing that simply ended.
    """
    port = fake_graph({'status': 200, 'body': {'value': []}},
                      {'status': 200, 'body': {'value': []}})
    port('/one')
    port('/two')

    with pytest.raises(AssertionError) as caught:
        port('/three')

    message = str(caught.value)
    assert '3' in message and '2' in message, (
        'the exhausted-script message %r states neither the number of calls '
        'nor the length of the script, so it cannot be acted on' % (message,))


def test_the_scripted_port_can_drive_the_no_request_was_sent_case(fake_graph):
    """The second envelope shape has to be playable, not merely loadable.

    BROWSE-05's evidence is a request that never happened. A port that could
    only return bodies could not put code under test into that state at all.
    """
    port = fake_graph(load_graph_envelope('business',
                                          'children_by_path_unencoded'))

    with pytest.raises(GraphTransportError) as caught:
        port('/drives/synthetic/root:/Round (2019) Việt:/children')

    assert 'InvalidURL' in str(caught.value), (
        'the raised transport failure %r does not name the error the capture '
        'recorded' % (str(caught.value),))
    assert port.paths, 'the failing call was not recorded'


def test_the_port_exposes_what_was_requested(fake_graph):
    """`paths` and `last_parameters` are the whole reason this is a recorder.

    BROWSE-04 and BROWSE-17 are both assertions about what was *asked for* --
    which expand, which filter -- not about what came back.
    """
    port = fake_graph({'status': 200, 'body': {'value': []}})

    port('/drives/synthetic/root/children',
         parameters={'expand': 'thumbnails'})

    assert port.paths == ['/drives/synthetic/root/children']
    assert port.last_parameters == {'expand': 'thumbnails'}


# ---------------------------------------------------------------------------
# The labelling gate (CI-02, CI-03, SETUP-05)
# ---------------------------------------------------------------------------

def test_every_fixture_sits_inside_exactly_one_drive_class_directory():
    fixtures = _graph_fixture_paths()
    assert len(fixtures) >= MINIMUM_FIXTURES, (
        'the scan found %d tracked fixture(s) under %s, fewer than the %d this '
        'set holds. A gate that found nothing certifies nothing; the prefix has '
        'probably moved' % (len(fixtures), GRAPH_FIXTURE_PREFIX,
                            MINIMUM_FIXTURES))

    hits = []
    for rel in fixtures:
        tail = PurePosixPath(rel[len(GRAPH_FIXTURE_PREFIX):])
        if str(tail) in UNLABELLED_ALLOWED:
            continue
        parts = tail.parts
        if len(parts) != 2 or parts[0] not in DRIVE_CLASSES:
            hits.append((rel, 1, 'not inside one of %r' % (DRIVE_CLASSES,)))

    assert not hits, (
        'these recorded responses do not say which kind of drive they came '
        'from. Six months from now nobody can name their source, and a Business '
        'result standing in for a Personal one is the substitution this rule '
        'exists to prevent -- the reserved-character sets genuinely differ:\n%s'
        % report(hits))


def test_both_drive_classes_are_represented():
    fixtures = _graph_fixture_paths()

    empty = []
    for drive_class in DRIVE_CLASSES:
        prefix = GRAPH_FIXTURE_PREFIX + drive_class + '/'
        if not any(rel.startswith(prefix) for rel in fixtures):
            empty.append(drive_class)

    assert not empty, (
        'the %s fixture directory is empty or gone. SETUP-05 paid for two test '
        'accounts so that both classes stay visible; a set collapsed to one '
        'class is a suite that can go green while the other kind of drive is '
        'broken' % ', '.join(empty))


def test_every_drive_class_names_a_directory_the_index_contains():
    """An entry that names nothing removes nothing -- and checks nothing.

    The same argument `test_every_exclusion_names_something_real` makes about
    `EXCLUDED_DOCS`, applied to the other list that can quietly stop working. A
    drive class nothing is filed under sits beside one holding half the set, and
    the difference is invisible without reading the tree.
    """
    fixtures = _graph_fixture_paths()
    present = {PurePosixPath(rel[len(GRAPH_FIXTURE_PREFIX):]).parts[0]
               for rel in fixtures
               if str(PurePosixPath(rel[len(GRAPH_FIXTURE_PREFIX):]))
               not in UNLABELLED_ALLOWED}

    missing = sorted(set(DRIVE_CLASSES) - present)
    assert not missing, (
        'DRIVE_CLASSES names %s, which the git index has no fixture directory '
        'for. Delete the entry, or record the responses it promises.'
        % ', '.join(missing))
