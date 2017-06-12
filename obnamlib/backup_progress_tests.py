# Copyright (C) 2017  Lars Wirzenius
#
# This program is free software: you can redistribute it and/or modify
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


import unittest

import obnamlib


class BackupProgressTests(unittest.TestCase):

    def test_initialised_properly(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        self.assertEqual(bp.file_count, 0)
        self.assertEqual(bp.backed_up_count, 0)
        self.assertEqual(bp.uploaded_bytes, 0)
        self.assertEqual(bp.scanned_bytes, 0)
        self.assertEqual(bp.started, None)
        self.assertFalse(bp.errors)

    def test_setting_what_records_started_time(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.what('foo')
        self.assertNotEqual(bp.started, None)

    def test_reporting_error_sets_errors_flag(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.error('foo')
        self.assertTrue(bp.errors)

    def test_files_get_counted(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.update_progress_with_file('foo', None)
        self.assertEqual(bp.file_count, 1)

    def test_scanned_bytes_get_counted(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.update_progress_with_scanned(12765)
        self.assertEqual(bp.scanned_bytes, 12765)

    def test_uploaded_bytes_get_counted(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.update_progress_with_upload(12765)
        self.assertEqual(bp.uploaded_bytes, 12765)

    def test_report_is_correct(self):
        ts = DummyTerminalStatus()
        bp = obnamlib.BackupProgress(ts)
        bp.set_time_func(lambda: 0)

        # Pretend we run a little backup of one file that is 1000
        # bytes in length and we need to upload it all.
        bp.what('backing up')
        bp.update_progress_with_file('foo', None)
        bp.update_progress_with_scanned(1000)
        bp.backed_up_count += 1
        bp.update_progress_with_upload(1000)

        # Fake VFS for the backup.
        fs = DummyFS()
        fs.bytes_written = 2000
        fs.bytes_read = 1000

        # Check that report is OK.
        bp.set_time_func(lambda: 10)
        r = bp.compute_report(fs)
        self.assertEqual(r['duration'], 10)
        self.assertEqual(r['file-count'], 1)
        self.assertEqual(r['backed-up-count'], 1)
        self.assertEqual(r['scanned-bytes'], 1000)
        self.assertEqual(r['uploaded-chunk-bytes'], 1000)
        self.assertEqual(r['uploaded-total-bytes'], 2000)
        self.assertEqual(r['downloaded-total-bytes'], 1000)
        self.assertEqual(r['overhead-total-bytes'], 2000 + 1000 - 1000)
        self.assertEqual(r['effective-upload-speed'], 1000.0 / 10.0)


class DummyTerminalStatus(object):

    def format(self, format):
        pass

    def flush(self):
        pass

    def error(self, msg):
        pass

    def __setitem__(self, key, value):
        pass


class DummyFS(object):

    def __init__(self):
        self.bytes_written = 0
        self.bytes_read = 0
