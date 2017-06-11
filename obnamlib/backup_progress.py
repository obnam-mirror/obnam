# Copyright (C) 2009-2015  Lars Wirzenius
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


import logging
import time

import obnamlib


class BackupProgress(object):

    def __init__(self, ts):
        self.file_count = 0
        self.backed_up_count = 0
        self.uploaded_bytes = 0
        self.scanned_bytes = 0
        self.started = None
        self.errors = False

        self._now = time.time

        self._ts = ts
        self._ts['current-file'] = ''
        self._ts['scanned-bytes'] = 0
        self._ts['uploaded-bytes'] = 0

        if self.ttystatus_supports_multiline():  # pragma: no cover
            self._ts.format(
                '%ElapsedTime() Backing up: '
                'found %Counter(current-file) files, '
                '%ByteSize(scanned-bytes); '
                'uploaded: %ByteSize(uploaded-bytes)\n'
                '%String(what)'
            )
        else:  # pragma: no cover
            self._ts.format(
                '%ElapsedTime() '
                '%Counter(current-file) '
                'files '
                '%ByteSize(scanned-bytes) scanned: '
                '%String(what)')

    def set_time_func(self, now):
        self._now = now

    def ttystatus_supports_multiline(self):
        return hasattr(self._ts, 'start_new_line')

    def clear(self):  # pragma: no cover
        self._ts.clear()

    def finish(self):  # pragma: no cover
        self._ts.finish()

    def error(self, msg, exc=None):
        self.errors = True

        logging.error(msg, exc_info=exc)
        self._ts.error('ERROR: %s' % msg)

    def what(self, what_what):
        if self.started is None:
            self.started = self._now()
        self._ts['what'] = what_what
        self._ts.flush()

    def update_progress(self):  # pragma: no cover
        self._ts['not-shown'] = 'not shown'

    def update_progress_with_file(self, filename, metadata):
        self._ts['what'] = filename
        self._ts['current-file'] = filename
        self.file_count += 1

    def update_progress_with_scanned(self, amount):
        self.scanned_bytes += amount
        self._ts['scanned-bytes'] = self.scanned_bytes

    def update_progress_with_upload(self, amount):
        self.uploaded_bytes += amount
        self._ts['uploaded-bytes'] = self.uploaded_bytes

    def update_progress_with_removed_checkpoint(self, gen):  # pragma: no cover
        self._ts['checkpoint'] = gen

    def compute_report(self, fs):
        duration = self._now() - self.started
        overhead = fs.bytes_written + fs.bytes_read - self.uploaded_bytes
        speed = self.uploaded_bytes / float(duration)

        return {
            'duration': duration,
            'file-count': self.file_count,
            'backed-up-count': self.backed_up_count,
            'scanned-bytes': self.scanned_bytes,
            'uploaded-chunk-bytes': self.uploaded_bytes,
            'uploaded-total-bytes': fs.bytes_written,
            'downloaded-total-bytes': fs.bytes_read,
            'overhead-total-bytes': overhead,
            'effective-upload-speed': speed,
        }

    def report_stats(self, output, fs, quiet, report=None):  # pragma: no cover
        if report is None:
            report = self.compute_report(fs)
            
        duration_string = obnamlib.humanise_duration(report['duration'])

        chunk_amount, chunk_unit = obnamlib.humanise_size(
            report['uploaded-total-bytes'])

        ul_amount, ul_unit = obnamlib.humanise_size(
            report['uploaded-total-bytes'])

        dl_amount, dl_unit = obnamlib.humanise_size(
            report['downloaded-total-bytes'])

        overhead_bytes = (
            report['downloaded-total-bytes'] +
            (report['uploaded-total-bytes'] - report['uploaded-total-bytes']))
        overhead_bytes = max(0, overhead_bytes)
        overhead_amount, overhead_unit = obnamlib.humanise_size(overhead_bytes)
        if report['uploaded-total-bytes'] > 0:
            overhead_percent = 100.0 * overhead_bytes / report['uploaded-total-bytes']
        else:
            overhead_percent = 0.0

        speed_amount, speed_unit = obnamlib.humanise_speed(
            report['uploaded-total-bytes'], report['duration'])

        logging.info(
            'Backup performance statistics:')
        logging.info(
            '* files found: %s',
            report['file-count'])
        logging.info(
            '* files backed up: %s',
            report['backed-up-count'])
        logging.info(
            '* uploaded chunk data: %s bytes (%s %s)',
            report['uploaded-total-bytes'], chunk_amount, chunk_unit)
        logging.info(
            '* total uploaded data (incl. metadata): %s bytes (%s %s)',
            report['uploaded-total-bytes'], ul_amount, ul_unit)
        logging.info(
            '* total downloaded data (incl. metadata): %s bytes (%s %s)',
            report['downloaded-total-bytes'], dl_amount, dl_unit)
        logging.info(
            '* transfer overhead: %s bytes (%s %s)',
            overhead_bytes, overhead_amount, overhead_unit)
        logging.info(
            '* duration: %s s (%s)',
            report['duration'], duration_string)
        logging.info(
            '* average speed: %s %s',
            speed_amount, speed_unit)

        scanned_amount, scanned_unit = obnamlib.humanise_size(
            report['scanned-bytes'])

        if not quiet:
            output.write(
                'Backed up %d files (of %d found), containing %.1f %s.\n' %
                (report['backed-up-count'],
                 report['file-count'],
                 scanned_amount,
                 scanned_unit))
            output.write(
                'Uploaded %.1f %s file data in %s at %.1f %s '
                'average speed.\n' %
                (chunk_amount,
                 chunk_unit,
                 duration_string,
                 speed_amount,
                 speed_unit))
            output.write(
                'Total download amount %.1f %s.\n' %
                (dl_amount,
                 dl_unit))
            output.write(
                'Total upload amount %.1f %s. '
                'Overhead was %.1f %s (%.1f %%).\n' %
                (ul_amount,
                 ul_unit,
                 overhead_amount,
                 overhead_unit,
                 overhead_percent))
