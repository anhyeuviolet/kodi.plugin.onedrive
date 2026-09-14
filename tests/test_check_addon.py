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
"""The checker exits zero on warnings; network retries must not weaken the gate."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.check_addon import check, verdict


CLEAN = 'INFO: We found no problems and no warnings, please enjoy your day.\n'
TIMEOUT = "WARN: HTTPSConnectionPool(host='github.com', port=443): Read timed out. (read timeout=5)\n"
SUMMARY = 'WARN: We found no problems and 1 warnings, please check the logfile.\n'
REPORT = TIMEOUT + SUMMARY
# Relevant frames from the Nexus CI failure on checker 0.0.36. The package
# constructor swallowed a failed repository fetch before initializing addons.
REPOSITORY_CRASH = '''INFO: Checking add-on plugin.onedrive.kn
Traceback (most recent call last):
  File "/opt/python/site-packages/kodi_addon_checker/check_addon_branches.py", line 43, in check_for_existing_addon
    if KodiVersion(branch) <= kodi_version and addon_name in repo:
  File "/opt/python/site-packages/kodi_addon_checker/addons/Repository.py", line 78, in __contains__
    for addon in self.addons:
                 ^^^^^^^^^^^
AttributeError: 'Repository' object has no attribute 'addons'
'''


@pytest.mark.parametrize('status,output,expected', [
    (0, CLEAN, 'clean'),
    (0, REPORT, 'retry'),
    (0, '\x1b[35m' + TIMEOUT.rstrip() + '\x1b[0m\n' + SUMMARY, 'retry'),
    (0, '', 'fail'),
    (1, CLEAN, 'fail'),
    (1, REPORT, 'fail'),
    (0, TIMEOUT, 'fail'),
    (0, SUMMARY, 'fail'),
    (0, 'WARN: File is not whitelisted\n' + SUMMARY, 'fail'),
    (0, TIMEOUT + 'WARN: File is not whitelisted\n' + SUMMARY.replace('1 warnings', '2 warnings'), 'fail'),
    (0, REPORT + 'PROBLEM: Invalid XML\n', 'fail'),
    (0, REPORT + 'ERROR: Check failed\n', 'fail'),
    (0, TIMEOUT + SUMMARY.replace('1 warnings', '2 warnings'), 'fail'),
    (0, 'INFO: Valid XML file found\n', 'fail'),
    (1, REPOSITORY_CRASH, 'retry'),
    (0, REPOSITORY_CRASH, 'fail'),
    (2, REPOSITORY_CRASH, 'fail'),
    (1, REPOSITORY_CRASH.replace('Repository.py', 'Other.py'), 'fail'),
    (1, REPOSITORY_CRASH.replace('kodi_addon_checker', 'plugin'), 'fail'),
    (1, REPOSITORY_CRASH.replace("'addons'", "'version'"), 'fail'),
    (1, "AttributeError: 'Repository' object has no attribute 'addons'\n", 'fail'),
    (1, 'WARN: Bad addon file\n' + REPOSITORY_CRASH, 'fail'),
    (1, 'PROBLEM: Invalid XML\n' + REPOSITORY_CRASH, 'fail'),
    (1, REPOSITORY_CRASH + 'RuntimeError: unrelated failure\n', 'fail'),
])
def test_report_classification(status, output, expected):
    assert verdict(status, output) == expected


@pytest.mark.parametrize('status,report', [(0, REPORT), (1, REPOSITORY_CRASH)])
def test_network_failure_then_clean_retries_and_keeps_each_report(tmp_path, status, report):
    run = Mock(side_effect=[SimpleNamespace(returncode=status, stdout=report),
                            SimpleNamespace(returncode=0, stdout=CLEAN)])
    sleep = Mock()
    assert check('piers', 'extracted/plugin.onedrive.kn', run=run, sleep=sleep,
                 log_dir=tmp_path) == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(10)
    assert (tmp_path / 'checker-piers-1.log').read_text() == report
    assert (tmp_path / 'checker-piers-2.log').read_text() == CLEAN
    assert run.call_args.args[0] == ['kodi-addon-checker', '--branch', 'piers',
                                   'extracted/plugin.onedrive.kn']


@pytest.mark.parametrize('status,report', [(0, REPORT), (1, REPOSITORY_CRASH)])
def test_repeated_network_failures_still_fail(tmp_path, status, report):
    run = Mock(return_value=SimpleNamespace(returncode=status, stdout=report))
    sleep = Mock()
    assert check('piers', 'addon', run=run, sleep=sleep, log_dir=tmp_path) == 1
    assert run.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [10, 20]


def test_real_warning_fails_without_retry(tmp_path):
    run = Mock(return_value=SimpleNamespace(returncode=0,
                                           stdout='WARN: Bad addon file\n' + SUMMARY))
    sleep = Mock()
    assert check('piers', 'addon', run=run, sleep=sleep, log_dir=tmp_path) == 1
    run.assert_called_once()
    sleep.assert_not_called()


def test_real_failure_after_timeout_is_not_retried(tmp_path):
    run = Mock(side_effect=[SimpleNamespace(returncode=0, stdout=REPORT),
                            SimpleNamespace(returncode=1, stdout='PROBLEM: Invalid XML\n')])
    sleep = Mock()
    assert check('piers', 'addon', run=run, sleep=sleep, log_dir=tmp_path) == 1
    assert run.call_count == 2
    sleep.assert_called_once_with(10)
