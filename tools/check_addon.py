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
"""Require a clean checker run; retry recognized network failures only."""

import argparse
from pathlib import Path
import re
import subprocess
import time


ANSI = re.compile(r'\x1b\[[0-9;]*m')
CLEAN = 'INFO: We found no problems and no warnings, please enjoy your day.'
SUMMARY = re.compile(r'^WARN: We found no problems and (\d+) warnings, please check the logfile\.$')
READ_TIMEOUT = re.compile(
    r"^WARN: HTTPS?ConnectionPool\(host='[^']+', port=\d+\): "
    r'Read timed out\. \(read timeout=[\d.]+\)$')
MISSING_REPOSITORY = "AttributeError: 'Repository' object has no attribute 'addons'"
REPOSITORY_FRAME = re.compile(
    r'^  File "[^"]*[/\\]kodi_addon_checker[/\\]addons[/\\]Repository\.py", '
    r'line \d+, in __contains__$')


def verdict(status, output):
    """Return clean, retry, or fail; unknown crashes and addon findings fail."""
    lines = ANSI.sub('', output).splitlines()
    warnings = [line for line in lines if line.startswith('WARN:')]
    if any(line.startswith(('ERROR:', 'PROBLEM:')) for line in lines):
        return 'fail'
    if status != 0:
        # Checker 0.0.36's Repository.__init__ catches RequestException and
        # returns before assigning self.addons. __contains__ then crashes when
        # checking branch indexes. Retry only that exact upstream failure, with
        # no addon warnings; other AttributeErrors remain immediate failures.
        frames = [line for line in lines if line.startswith('  File "')]
        if (status == 1 and not warnings and frames
                and 'Traceback (most recent call last):' in lines
                and REPOSITORY_FRAME.fullmatch(frames[-1])
                and '    for addon in self.addons:' in lines
                and lines[-1] == MISSING_REPOSITORY):
            return 'retry'
        return 'fail'
    if not warnings:
        return 'clean' if CLEAN in lines else 'fail'
    summaries = [SUMMARY.fullmatch(line) for line in warnings]
    summaries = [match for match in summaries if match]
    details = [line for line in warnings if not SUMMARY.fullmatch(line)]
    if (len(summaries) == 1 and details
            and int(summaries[0].group(1)) == len(details)
            and all(READ_TIMEOUT.fullmatch(line) for line in details)):
        return 'retry'
    return 'fail'


def check(branch, addon, *, run=None, sleep=None, log_dir=Path('.')):
    run = run or subprocess.run
    sleep = sleep or time.sleep
    for attempt in range(1, 4):
        print('Checker %s: attempt %d/3' % (branch, attempt), flush=True)
        result = run(['kodi-addon-checker', '--branch', branch, str(addon)],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, encoding='utf-8', errors='replace')
        output = ANSI.sub('', result.stdout)
        (log_dir / ('checker-%s-%d.log' % (branch, attempt))).write_text(
            output, encoding='utf-8')
        print(output, end='' if output.endswith('\n') else '\n', flush=True)
        print('checker exited %d' % result.returncode, flush=True)
        outcome = verdict(result.returncode, output)
        if outcome == 'clean':
            return 0
        if outcome == 'retry' and attempt < 3:
            delay = attempt * 10
            print('Recognized checker network failure; retrying in %ds.' % delay,
                  flush=True)
            sleep(delay)
            continue
        print('::error::Checker %s did not complete with zero problems and zero '
              'warnings%s.' % (branch, ' after 3 attempts' if attempt == 3 else ''),
              flush=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branch', required=True, choices=('nexus', 'omega', 'piers'))
    parser.add_argument('addon', type=Path)
    args = parser.parse_args()
    return check(args.branch, args.addon)


if __name__ == '__main__':
    raise SystemExit(main())
