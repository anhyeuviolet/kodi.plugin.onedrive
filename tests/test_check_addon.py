"""The checker exits zero on warnings; network retries must not weaken the gate."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.check_addon import check, verdict


CLEAN = 'INFO: We found no problems and no warnings, please enjoy your day.\n'
TIMEOUT = "WARN: HTTPSConnectionPool(host='github.com', port=443): Read timed out. (read timeout=5)\n"
SUMMARY = 'WARN: We found no problems and 1 warnings, please check the logfile.\n'
REPORT = TIMEOUT + SUMMARY


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
])
def test_report_classification(status, output, expected):
    assert verdict(status, output) == expected


def test_timeout_then_clean_retries_and_keeps_each_report(tmp_path):
    run = Mock(side_effect=[SimpleNamespace(returncode=0, stdout=REPORT),
                            SimpleNamespace(returncode=0, stdout=CLEAN)])
    sleep = Mock()
    assert check('piers', 'extracted/plugin.onedrive.kn', run=run, sleep=sleep,
                 log_dir=tmp_path) == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(10)
    assert (tmp_path / 'checker-piers-1.log').read_text() == REPORT
    assert (tmp_path / 'checker-piers-2.log').read_text() == CLEAN
    assert run.call_args.args[0] == ['kodi-addon-checker', '--branch', 'piers',
                                   'extracted/plugin.onedrive.kn']


def test_repeated_timeouts_still_fail(tmp_path):
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=REPORT))
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
