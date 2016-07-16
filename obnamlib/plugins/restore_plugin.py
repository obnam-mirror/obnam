# Copyright (C) 2009-2016  Lars Wirzenius
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


import hashlib
import logging
import os
import stat
import time

import obnamlib


class WrongNumberOfGenerationSettingsError(obnamlib.ObnamError):

    msg = 'The restore command wants exactly one generation option'


class NoToError(obnamlib.ObnamError):

    msg = 'The restore command wants a target set with --to'


class RestoreErrors(obnamlib.ObnamError):

    msg = '''There were errors when restoring

    See previous error messages for details.

    '''


class RestoreTargetNotEmpty(obnamlib.ObnamError):

    msg = '''The restore --to directory ({to}) is not empty.'''


class Hardlinks(object):

    '''Keep track of inodes with unrestored hardlinks.'''

    def __init__(self):
        self.inodes = dict()

    def key(self, metadata):
        return '%s:%s' % (metadata.st_dev, metadata.st_ino)

    def add(self, filename, metadata):
        self.inodes[self.key(metadata)] = (filename, metadata.st_nlink)

    def filename(self, metadata):
        key = self.key(metadata)
        if key in self.inodes:
            return self.inodes[key][0]
        else:
            return None

    def forget(self, metadata):
        key = self.key(metadata)
        filename, nlinks = self.inodes[key]
        if nlinks <= 2:
            del self.inodes[key]
        else:
            self.inodes[key] = (filename, nlinks - 1)


class RestorePlugin(obnamlib.ObnamPlugin):

    # A note about the implementation: we need to make sure all the
    # files we restore go into the target directory. We do this by
    # prefixing all filenames we write to with './', and then using
    # os.path.join to put the target directory name at the beginning.
    # The './' business is necessary because os.path.join(a,b) returns
    # just b if b is an absolute path.

    def enable(self):
        self.app.add_subcommand(
            'restore',
            self.restore,
            arg_synopsis='[DIRECTORY]...')
        self.app.settings.string(
            ['to'],
            'where to restore or FUSE mount; '
            'for restores, must be empty or must not exist')
        self.app.settings.string_list(
            ['generation'],
            'which generation to restore',
            default=['latest'])
        self.app.settings.boolean(
            ['always-restore-setuid'],
            'restore setuid/setgid bits in restored files, '
            'even if not root or backed up file had different owner '
            'than user running restore',
            default=False)

    @property
    def write_ok(self):
        return not self.app.settings['dry-run']

    def configure_ttystatus(self):
        self.app.ts['current'] = ''
        self.app.ts['total'] = 0
        self.app.ts['current-bytes'] = 0
        self.app.ts['total-bytes'] = 0

        self.app.ts.format('%RemainingTime(current-bytes,total-bytes) '
                           '%Counter(current) files '
                           '%ByteSize(current-bytes) '
                           '(%PercentDone(current-bytes,total-bytes)) '
                           '%ByteSpeed(current-bytes) '
                           '%Pathname(current)')

    def restore(self, args):
        '''Restore some or all files from a generation.'''
        self.app.settings.require('repository')
        self.app.settings.require('client-name')
        self.app.settings.require('generation')
        self.app.settings.require('to')

        if not self.app.settings['to']:
            raise NoToError()

        logging.debug(
            'restoring generation %s', self.app.settings['generation'])
        logging.debug('restoring to %s', self.app.settings['to'])

        logging.debug('restoring what: %s', repr(args))
        if not args:
            logging.debug('no args given, so restoring everything')
            args = ['/']

        self.downloaded_bytes = 0
        self.file_count = 0
        self.started = time.time()

        self.repo = self.app.get_repository_object()
        client_name = self.app.settings['client-name']

        if self.write_ok:
            self.fs = self.app.fsf.new(self.app.settings['to'], create=True)
            self.fs.connect()

            # The --to directory MUST be empty, to prevent users from
            # accidentally restoring over /.
            if self.fs.listdir('.') != []:
                raise RestoreTargetNotEmpty(to=self.app.settings['to'])

            # Set permissions on this directory to be quite
            # restrictive, so that nobody else can access the files
            # while the restore is happening. The directory named by
            # --to is set to have the permissions of the filesystem
            # root directory (/) in the backup as the final step, so
            # the permissions will eventually be correct.
            self.fs.chmod_not_symlink('.', 0700)
        else:
            self.fs = None  # this will trigger error if we try to really write

        self.hardlinks = Hardlinks()

        self.errors = False

        generations = self.app.settings['generation']
        if len(generations) != 1:
            raise WrongNumberOfGenerationSettingsError()
        gen = self.repo.interpret_generation_spec(client_name, generations[0])

        self.configure_ttystatus()
        self.app.ts['total'] = self.repo.get_generation_key(
            gen, obnamlib.REPO_GENERATION_FILE_COUNT)
        self.app.ts['total-bytes'] = self.repo.get_generation_key(
            gen, obnamlib.REPO_GENERATION_TOTAL_DATA)

        self.app.dump_memory_profile('at beginning after setup')

        for arg in args:
            self.restore_something(gen, arg)
            self.app.dump_memory_profile('at restoring %s' % repr(arg))

        if self.write_ok:
            self.fs.close()
            self.repo.close()

        self.app.ts.clear()
        self.report_stats()

        self.app.ts.finish()

        if self.errors:
            raise RestoreErrors()

    def restore_something(self, gen, root):
        for pathname in self.repo.walk_generation(gen, root):
            self.file_count += 1
            self.app.ts['current'] = pathname
            self.restore_safely(gen, pathname)

    def restore_safely(self, gen, pathname):
        try:
            dirname = os.path.dirname(pathname)
            if self.write_ok and not self.fs.exists('./' + dirname):
                self.fs.makedirs('./' + dirname)

            metadata = self.repo.get_metadata_from_file_keys(gen, pathname)

            set_metadata = True
            if metadata.isdir():
                self.restore_dir(gen, pathname, metadata)
            elif metadata.islink():
                self.restore_symlink(gen, pathname, metadata)
            elif metadata.st_nlink > 1:
                link = self.hardlinks.filename(metadata)
                if link:
                    self.restore_hardlink(pathname, link, metadata)
                    set_metadata = False
                else:
                    self.hardlinks.add(pathname, metadata)
                    self.restore_first_link(gen, pathname, metadata)
            else:
                self.restore_first_link(gen, pathname, metadata)
            if set_metadata and self.write_ok:
                always = self.app.settings['always-restore-setuid']
                try:
                    obnamlib.set_metadata(
                        self.fs, './' + pathname, metadata,
                        always_set_id_bits=always)
                except obnamlib.SetMetadataError as e:
                    self.app.ts.error(str(e))
                    self.errors = True
        except Exception, e:  # pylint: disable=broad-except
            # Reaching this code path means we've hit a bug, so we log
            # a full traceback.
            msg = "Failed to restore %s:" % (pathname,)
            logging.exception(msg)
            self.app.ts.error(msg + " " + str(e))
            self.errors = True

    def restore_dir(self, gen, root, metadata):
        logging.debug('restoring dir %s', root)
        if self.write_ok:
            if not self.fs.exists('./' + root):
                self.fs.mkdir('./' + root)
        self.app.dump_memory_profile(
            'after recursing through %s' % repr(root))

    def restore_hardlink(self, filename, link, metadata):
        logging.debug('restoring hardlink %s to %s', filename, link)
        if self.write_ok:
            self.fs.link('./' + link, './' + filename)
            self.hardlinks.forget(metadata)

    def restore_symlink(self, gen, filename, metadata):
        logging.debug('restoring symlink %r -> %r', filename, metadata.target)

    def restore_first_link(self, gen, filename, metadata):
        if stat.S_ISREG(metadata.st_mode):
            self.restore_regular_file(gen, filename, metadata)
        elif stat.S_ISFIFO(metadata.st_mode):
            self.restore_fifo(gen, filename, metadata)
        elif stat.S_ISSOCK(metadata.st_mode):
            self.restore_socket(gen, filename, metadata)
        elif stat.S_ISBLK(metadata.st_mode) or stat.S_ISCHR(metadata.st_mode):
            self.restore_device(gen, filename, metadata)
        else:
            msg = ('Unknown file type: %s (%o)' %
                   (filename, metadata.st_mode))
            logging.error(msg)
            self.app.ts.notify(msg)

    def restore_regular_file(self, gen, filename, metadata):
        logging.debug('restoring regular %s', filename)
        if self.write_ok:
            f = self.fs.open('./' + filename, 'wb')
            if obnamlib.REPO_FILE_MD5 in self.repo.get_allowed_file_keys():
                summer = hashlib.md5()
            else:
                summer = None

            try:
                chunkids = self.repo.get_file_chunk_ids(gen, filename)
                self.restore_chunks(f, chunkids, summer)
            except obnamlib.MissingFilterError, e:
                msg = '%s: %s' % (filename, str(e))
                logging.error(msg)
                self.app.ts.notify(msg)
                self.errors = True
            f.close()

            correct_checksum = metadata.md5
            if summer and summer.digest() != correct_checksum:
                msg = 'File checksum restore error: %s' % filename
                msg += ' (%s vs %s)' % (
                    summer.hexdigest(), correct_checksum.encode('hex'))
                logging.error(msg)
                self.app.ts.notify(msg)
                self.errors = True

    def restore_chunks(self, f, chunkids, checksummer):
        zeroes = ''
        hole_at_end = False
        for chunkid in chunkids:
            data = self.repo.get_chunk_content(chunkid)
            self.verify_chunk_checksum(data, chunkid)
            if checksummer:
                checksummer.update(data)
            self.downloaded_bytes += len(data)
            if len(data) != len(zeroes):
                zeroes = '\0' * len(data)
            if data == zeroes:
                f.seek(len(data), 1)
                hole_at_end = True
            else:
                f.write(data)
                hole_at_end = False
            self.app.ts['current-bytes'] += len(data)
        if hole_at_end:
            pos = f.tell()
            if pos > 0:
                f.seek(-1, 1)
                f.write('\0')

    def verify_chunk_checksum(self, data, chunk_id):
        # FIXME: RepositoryInterface doesn't currently seem to provide
        # the necessary tools for implementing this method. So
        # currently we do nothing. Later, this should be fixed.
        #
        # We used to call the validate_chunk_content method, but that
        # doesn't do the right thing, but does cause the chunk data to
        # be downloaded twice.
        pass

    def restore_fifo(self, gen, filename, metadata):
        logging.debug('restoring fifo %s', filename)
        if self.write_ok:
            self.fs.mknod('./' + filename, metadata.st_mode)

    def restore_socket(self, gen, filename, metadata):
        logging.debug('restoring socket %s', filename)
        if self.write_ok:
            self.fs.mknod('./' + filename, metadata.st_mode)

    def restore_device(self, gen, filename, metadata):
        logging.debug('restoring device %s', filename)
        if self.write_ok:
            self.fs.mknod('./' + filename, metadata.st_mode)

    def report_stats(self):
        duration = time.time() - self.started
        size_amount, size_unit = obnamlib.humanise_size(
            self.downloaded_bytes)
        speed_amount, speed_unit = obnamlib.humanise_speed(
            self.downloaded_bytes, duration)
        duration_string = obnamlib.humanise_duration(duration)

        logging.info('Restore performance statistics:')
        logging.info('* files restored: %s', self.file_count)
        logging.info(
            '* downloaded data: %s bytes (%s %s)',
            self.downloaded_bytes, size_amount, size_unit)
        logging.info('* duration: %s s', duration)
        logging.info('* average speed: %s %s', speed_amount, speed_unit)
        self.app.ts.notify(
            'Restored %d files, '
            'downloaded %.1f %s in %s at %.1f %s average speed' %
            (self.file_count,
             size_amount, size_unit,
             duration_string, speed_amount, speed_unit))
