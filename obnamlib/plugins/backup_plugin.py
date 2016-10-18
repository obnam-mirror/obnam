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


import errno
import logging
import os
import re
import stat
import traceback
import urlparse

import larch
import tracing

import obnamlib


class RepositorySettingMissingError(obnamlib.ObnamError):

    msg = ('No --repository setting. '
           'You need to specify it on the command line or '
           'a configuration file')


class BackupRootMissingError(obnamlib.ObnamError):

    msg = 'No backup roots specified'


class BackupRootDoesNotExist(obnamlib.ObnamError):

    msg = 'Backup root does not exist or is not a directory: {root}'


class BackupErrors(obnamlib.ObnamError):

    msg = 'There were errors during the backup'


class CheckpointManager(object):

    def __init__(self, repo, checkpoint_interval):
        self.repo = repo
        self.interval = checkpoint_interval
        self.clear()

    def add_checkpoint(self, generation_id):
        self.checkpoints.append(generation_id)
        self.last_checkpoint = self.repo.get_fs().bytes_written

    def clear(self):
        self.checkpoints = []
        self.last_checkpoint = 0

    def time_for_checkpoint(self):
        bytes_since = (self.repo.get_fs().bytes_written -
                       self.last_checkpoint)
        return bytes_since >= self.interval


class BackupPlugin(obnamlib.ObnamPlugin):

    def enable(self):
        self.app.add_subcommand(
            'backup', self.backup, arg_synopsis='[DIRECTORY|URL]...')
        self.add_backup_settings()
        self.app.hooks.new('backup-finished')
        self.app.hooks.new('backup-exclude')

    def add_backup_settings(self):

        # Backup related settings.

        backup_group = obnamlib.option_group['backup'] = 'Backing up'

        self.app.settings.string_list(
            ['root'],
            'what to backup',
            metavar='URL',
            group=backup_group)

        self.app.settings.bytesize(
            ['checkpoint'],
            'make a checkpoint after a given SIZE',
            metavar='SIZE',
            default=1024**3,
            group=backup_group)

        self.app.settings.choice(
            ['deduplicate'],
            ['fatalist', 'never', 'verify'],
            'find duplicate data in backed up data '
            'and store it only once; three modes '
            'are available: never de-duplicate, '
            'verify that no hash collisions happen, '
            'or (the default) fatalistically accept '
            'the risk of collisions',
            metavar='MODE',
            group=backup_group)

        self.app.settings.boolean(
            ['leave-checkpoints'],
            'leave checkpoint generations at the end '
            'of a successful backup run',
            group=backup_group)

        self.app.settings.boolean(
            ['small-files-in-btree'],
            'this is available only for backwards compatibility; '
            'do not use it, and remove it from your configuration',
            group=backup_group)

        # Performance related settings.

        perf_group = obnamlib.option_group['perf']

        self.app.settings.integer(
            ['chunkids-per-group'],
            'encode NUM chunk ids per group',
            metavar='NUM',
            default=obnamlib.DEFAULT_CHUNKIDS_PER_GROUP,
            group=perf_group)

        # Development related settings.

        devel_group = obnamlib.option_group['devel']

        self.app.settings.string_list(
            ['testing-fail-matching'],
            'development testing helper: simulate failures during backup '
            'for files that match the given regular expressions',
            metavar='REGEXP',
            group=devel_group)

    def backup(self, args):
        '''Backup data to repository.

        Live data location must be a directory, but can be either a
        local pathname or a supported URL (sftp).

        '''

        logging.info('Backup starts')

        root_urls = self.app.settings['root'] + args
        self.check_for_required_settings(root_urls)
        self.pretend = self.app.settings['pretend']

        self.start_backup()
        try:
            if not self.pretend:
                self.start_generation()
            self.backup_roots(root_urls)
            if not self.pretend:
                self.finish_generation()
                if self.should_remove_checkpoints():
                    self.remove_checkpoints()
            self.finish_backup(args)
        except BaseException, e:
            logging.debug('Handling exception %s', str(e))
            logging.debug(traceback.format_exc())
            self.unlock_when_error()
            raise

        if self.progress.errors:
            raise BackupErrors()

    def check_for_required_settings(self, roots):
        self.app.settings.require('repository')
        self.app.settings.require('client-name')

        if not self.app.settings['repository']:
            raise RepositorySettingMissingError()

        if not roots:
            raise BackupRootMissingError()

    def start_backup(self):
        self.configure_progress_reporting()
        self.progress.what('setting up')

        self.memory_dump_counter = 0
        self.chunkid_token_map = obnamlib.ChunkIdTokenMap()

        self.progress.what('connecting to repository')
        self.repo = self.open_repository()
        if not self.pretend:
            self.prepare_repository_for_client()

        self.checkpoint_manager = CheckpointManager(
            self.repo,
            self.app.settings['checkpoint'])

    def configure_progress_reporting(self):
        self.progress = obnamlib.BackupProgress(self.app.ts)

    def open_repository(self):
        if self.pretend:
            try:
                return self.app.get_repository_object()
            except Exception:
                self.progress.error(
                    'Are you using --pretend without an existing '
                    'repository? That does not\n'
                    'work, sorry. You can create a small repository, '
                    'backing up just one\n'
                    'small directory, and then use --pretend with '
                    'the real data.')
                raise
        else:
            return self.app.get_repository_object(create=True)

    def prepare_repository_for_client(self):
        self.progress.what('adding client')
        self.add_client(self.client_name)

        self.progress.what('locking client')
        self.repo.lock_client(self.client_name)

        # Need to lock the shared stuff briefly, so encryption etc
        # gets initialized.
        self.progress.what('initialising shared directories')
        self.repo.lock_chunk_indexes()
        self.repo.unlock_chunk_indexes()

    def start_generation(self):
        self.progress.what('starting new generation')
        self.new_generation = self.repo.create_generation(self.client_name)

    def finish_generation(self):
        prefix = 'committing changes to repository: '

        self.progress.what(prefix + 'locking shared chunk indexes')
        self.repo.lock_chunk_indexes()

        self.progress.what(prefix + 'adding chunks to shared chunk indexes')
        self.add_chunks_to_shared()

        self.progress.what(prefix + 'updating generation metadata')
        self.repo.set_generation_key(
            self.new_generation,
            obnamlib.REPO_GENERATION_FILE_COUNT,
            self.progress.file_count)
        self.repo.set_generation_key(
            self.new_generation,
            obnamlib.REPO_GENERATION_TOTAL_DATA,
            self.progress.scanned_bytes)
        self.repo.set_generation_key(
            self.new_generation,
            obnamlib.REPO_GENERATION_IS_CHECKPOINT,
            False)

        self.progress.what(prefix + 'committing client')
        self.repo.flush_chunks()
        self.repo.commit_client(self.client_name)
        self.repo.unlock_client(self.client_name)

        self.progress.what(prefix + 'committing shared chunk indexes')
        self.repo.commit_chunk_indexes()
        self.repo.unlock_chunk_indexes()

    def should_remove_checkpoints(self):
        return (not self.progress.errors and
                not self.app.settings['leave-checkpoints'])

    def remove_checkpoints(self):
        prefix = 'removing checkpoints'
        self.progress.what(prefix)

        self.repo.lock_everything()

        for gen in self.checkpoint_manager.checkpoints:
            self.progress.update_progress_with_removed_checkpoint(gen)
            self.repo.remove_generation(gen)

        self.progress.what(prefix + ': committing client')
        self.repo.commit_client(self.client_name)
        self.repo.unlock_client(self.client_name)

        self.progress.what(prefix + ': committing shared chunk indexes')
        self.repo.commit_chunk_indexes()

        self.progress.what(prefix + ': removing unused chunks')
        self.repo.remove_unused_chunks()

        self.repo.unlock_everything()

    def finish_backup(self, args):
        self.progress.what('closing connection to repository')
        self.repo.close()

        self.progress.clear()
        self.progress.finish()
        self.progress.report_stats(
            self.app.output, self.repo.get_fs(), self.app.settings['quiet'])

        logging.info('Backup finished.')
        self.app.hooks.call('backup-finished', args, self.progress)
        self.app.dump_memory_profile('at end of backup run')

    def parse_checkpoint_size(self, value):
        p = obnamlib.ByteSizeParser()
        p.set_default_unit('MiB')
        return p.parse(value)

    @property
    def client_name(self):
        return self.app.settings['client-name']

    def unlock_when_error(self):
        try:
            if self.repo.got_client_lock(self.client_name):
                logging.info('Attempting to unlock client because of error')
                self.repo.unlock_client(self.client_name)
            if self.repo.got_chunk_indexes_lock():
                logging.info(
                    'Attempting to unlock shared trees because of error')
                self.repo.unlock_chunk_indexes()
        except BaseException, e2:
            logging.warning('Error while unlocking due to error: %s', str(e2))
            logging.debug(traceback.format_exc())
        else:
            logging.info('Successfully unlocked')

    def add_chunks_to_shared(self):
        for chunkid, token in self.chunkid_token_map:
            self.repo.put_chunk_into_indexes(chunkid, token, self.client_name)
        self.chunkid_token_map.clear()

    def add_client(self, client_name):
        try:
            self.repo.lock_client_list()
        except obnamlib.GpgError:
            self.repo.unlock_client_list()
            raise

        if client_name not in self.repo.get_client_names():
            tracing.trace('adding new client %s' % client_name)
            tracing.trace('client list before adding: %s' %
                          self.repo.get_client_names())
            self.repo.add_client(client_name)
            tracing.trace('client list after adding: %s' %
                          self.repo.get_client_names())
        self.repo.commit_client_list()
        self.repo.unlock_client_list()
        self.repo = self.app.get_repository_object(repofs=self.repo.get_fs())

    def backup_roots(self, root_urls):
        self.progress.what('connecting to repository')
        self.open_fs(root_urls[0])
        absroots = self.find_absolute_roots(root_urls)
        if not self.pretend:
            self.remove_old_roots(absroots)
        self.checkpoint_manager.clear()
        for root_url in root_urls:
            self.backup_root(root_url, absroots)
        if self.fs:
            self.fs.close()

    def backup_root(self, root, absroots):
        logging.info('Backing up root %s', root)
        self.progress.what('connecting to live data %s' % root)

        self.reopen_fs(root)

        self.progress.what('scanning for files in %s' % root)
        absroot = self.fs.abspath('.')

        # If the root is a file, we can just back up the file.
        if os.path.isfile(root):
            self.just_one_file = os.path.join(absroot, os.path.split(root)[1])
        else:
            self.just_one_file = None

        self.root_metadata = self.fs.lstat(absroot)

        num_dirs = 0
        flush_threshold = 1000

        for pathname, metadata in self.find_files(absroot):
            logging.info('Backing up %s', pathname)

            if not self.pretend:
                existed = self.repo.file_exists(self.new_generation, pathname)
            try:
                self.maybe_simulate_error(pathname)
                if stat.S_ISDIR(metadata.st_mode):
                    self.backup_directory(pathname, metadata, absroots)
                else:
                    self.backup_non_directory(pathname, metadata)
            except (IOError, OSError) as e:
                e2 = self.translate_enverror_to_obnamerror(pathname, e)
                msg = 'Can\'t back up %s: %s' % (pathname, str(e2))
                self.progress.error(msg, exc=e)
                if not existed and not self.pretend:
                    self.remove_partially_backed_up_file(pathname)
                if e.errno in (errno.ENOSPC, errno.EPIPE):
                    raise

            if metadata.isdir() and not self.pretend:
                num_dirs += 1
                if num_dirs >= flush_threshold:
                    self.repo.flush_client(self.client_name)
                    self.app.dump_memory_profile('after flushing client')
                    num_dirs = 0

            if self.checkpoint_manager.time_for_checkpoint():
                self.make_checkpoint()
                self.progress.what(pathname)
                num_dirs = 0

        self.backup_parents('.')

    def translate_enverror_to_obnamerror(self, pathname, exc):
        if isinstance(exc, IOError):
            return obnamlib.ObnamIOError(
                errno=exc.errno,
                strerror=exc.strerror,
                filename=exc.filename or pathname)
        else:
            return obnamlib.ObnamSystemError(
                errno=exc.errno,
                strerror=exc.strerror,
                filename=exc.filename or pathname)

    def backup_directory(self, pathname, metadata, absroots):
        # Directories should only be counted in the progress their
        # metadata has changed. This covers the case when files have
        # been deleted from them.
        gen = self.get_current_generation()
        if self.metadata_has_changed(gen, pathname, metadata):
            self.progress.backed_up_count += 1

        self.backup_dir_contents(pathname, no_delete_paths=absroots)
        self.backup_metadata(pathname, metadata)

    def backup_non_directory(self, pathname, metadata):
        # Non-directories' progress can be updated without further
        # thinking.
        self.progress.backed_up_count += 1

        self.backup_metadata(pathname, metadata)
        if stat.S_ISREG(metadata.st_mode):
            self.backup_file_contents(pathname, metadata)
        self.backup_metadata(pathname, metadata)

    def open_fs(self, root_url):
        def func(url):
            self.fs = self.app.fsf.new(url)
            self.fs.connect()
        self.open_or_reopen_fs(func, root_url)

    def reopen_fs(self, root_url):
        self.open_or_reopen_fs(self.fs.reinit, root_url)

    def open_or_reopen_fs(self, func, root_url):
        try:
            func(root_url)
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise BackupRootDoesNotExist(root=root_url)
            raise

    def find_absolute_roots(self, root_urls):
        absroots = []
        for root_url in root_urls:
            self.progress.what('determining absolute path for %s' % root_url)

            scheme, netloc, path, params, query, fragment = \
                urlparse.urlparse(root_url)

            if self.fs.isdir(path):
                new_url = root_url
            else:
                parent_path = os.path.dirname(path)
                new_url = urlparse.urlunparse(
                    (scheme, netloc, parent_path, params, query, fragment))

            self.fs.reinit(new_url)
            absroots.append(self.fs.abspath('.'))

        return absroots

    def remove_partially_backed_up_file(self, pathname):
        try:
            self.repo.remove_file(self.new_generation, pathname)
        except KeyError:
            # File removal failed, but ignore that.
            # FIXME: This is an artifact of implementation
            # details of the old repository class. Should
            # be cleaned up, someday.
            pass
        except (OSError, IOError, obnamlib.ObnamError) as ee:
            msg = (
                'Error removing partly backed up file %s: %s'
                % (pathname, repr(ee)))
            self.progress.error(msg, ee)

    def maybe_simulate_error(self, pathname):
        '''Raise an IOError if specified by --testing-fail-matching.'''

        for pattern in self.app.settings['testing-fail-matching']:
            if re.search(pattern, pathname):
                e = errno.ENOENT
                raise IOError(e, os.strerror(e), pathname)

    def make_checkpoint(self):
        logging.info('Making checkpoint')
        self.progress.what('making checkpoint')
        if not self.pretend:
            self.checkpoint_manager.add_checkpoint(self.new_generation)

            self.progress.what('making checkpoint: backing up parents')
            self.backup_parents('.')

            self.progress.what(
                'making checkpoint: locking shared chunk indexes')
            self.repo.lock_chunk_indexes()

            self.progress.what(
                'making checkpoint: adding chunks to shared chunk indexes')
            self.add_chunks_to_shared()

            self.progress.what(
                'making checkpoint: committing per-client data')
            self.repo.set_generation_key(
                self.new_generation,
                obnamlib.REPO_GENERATION_IS_CHECKPOINT, 1)
            self.repo.flush_chunks()
            self.repo.commit_client(self.client_name)
            self.repo.unlock_client(self.client_name)

            self.progress.what(
                'making checkpoint: committing shared chunk indexes')
            self.repo.commit_chunk_indexes()
            self.repo.unlock_chunk_indexes()
            self.last_checkpoint = self.repo.get_fs().bytes_written

            self.progress.what('making checkpoint: re-opening repository')
            self.repo = self.app.get_repository_object(
                repofs=self.repo.get_fs())

            self.progress.what('making checkpoint: starting a new generation')
            self.repo.lock_client(self.client_name)
            self.new_generation = self.repo.create_generation(
                self.client_name)
            self.app.dump_memory_profile('at end of checkpoint')

            self.progress.what('making checkpoint: continuing backup')

    def find_files(self, root):
        '''Find all files and directories that need to be backed up.

        This is a generator. It yields (pathname, metadata) pairs.

        The caller should not recurse through directories, just backup
        the directory itself (name, metadata, file list).

        '''

        for pathname, st in self.fs.scan_tree(root, ok=self.can_be_backed_up):
            tracing.trace('considering %s' % pathname)
            try:
                metadata = obnamlib.read_metadata(self.fs, pathname, st=st)
                self.progress.update_progress_with_file(pathname, metadata)
                if self.needs_backup(pathname, metadata):
                    yield pathname, metadata
                else:
                    self.progress.update_progress_with_scanned(
                        metadata.st_size)
            except GeneratorExit:
                raise
            except KeyboardInterrupt:
                logging.error('Keyboard interrupt')
                raise
            except BaseException, e:
                msg = 'Cannot back up %s: %s' % (pathname, str(e))
                self.progress.error(msg, e)

    def can_be_backed_up(self, pathname, st):
        if self.just_one_file:
            return pathname == self.just_one_file

        exclude = [False]
        self.app.hooks.call(
            'backup-exclude',
            progress=self.progress,
            fs=self.fs,
            pathname=pathname,
            stat_result=st,
            root_metadata=self.root_metadata,
            exclude=exclude)
        if exclude[0]:
            return False

        return True

    def needs_backup(self, pathname, current):
        '''Does a given file need to be backed up?'''

        # Directories always require backing up so that backup_dir_contents
        # can remove stuff that no longer exists from them.
        if current.isdir():
            tracing.trace('%s is directory, so needs backup' % pathname)
            return True

        gen = self.get_current_generation()
        tracing.trace('gen=%s' % repr(gen))
        return self.metadata_has_changed(gen, pathname, current)

    def get_current_generation(self):
        '''Return the current generation.

        This handles pretend-mode correctly (in pretend-mode we don't
        have self.new_generation).

        '''

        if self.pretend:
            gens = self.repo.get_client_generation_ids(self.client_name)
            assert gens, "Can't handle --pretend without generations"
            return gens[-1]
        else:
            return self.new_generation

    def metadata_has_changed(self, gen, pathname, current):
        '''Has the metadata for pathname changed since given generation?

        Treat a file that didn't exist in the generation as changed.

        '''

        try:
            old = self.get_metadata_from_generation(gen, pathname)
        except obnamlib.ObnamError:
            # File does not exist in the previous generation, so it
            # does need to be backed up.
            return True

        must_be_equal = (
            'st_mtime_sec',
            'st_mtime_nsec',
            'st_mode',
            'st_nlink',
            'st_size',
            'st_uid',
            'st_gid',
            )

        for field in must_be_equal:
            current_value = getattr(current, field)
            old_value = getattr(old, field)
            if current_value != old_value:
                return True

        # Treat xattr values None (no extended attributes) and ''
        # (there are no values, but the xattr blob exists as an empty
        # string) as equal values.
        xattr_current = current.xattr or None
        xattr_old = old.xattr or None
        if xattr_current != xattr_old:
            return True

        return False

    def get_metadata_from_generation(self, gen, pathname):
        return self.repo.get_metadata_from_file_keys(gen, pathname)

    def add_file_to_generation(self, filename, metadata):
        self.repo.add_file(self.new_generation, filename)
        self.repo.set_file_keys_from_metadata(
            self.new_generation, filename, metadata)

    def backup_parents(self, root):
        '''Back up parents of root, non-recursively.'''
        root = self.fs.abspath(root)
        tracing.trace('backing up parents of %s', root)

        dummy_metadata = obnamlib.Metadata(st_mode=0777 | stat.S_IFDIR)

        while True:
            parent = os.path.dirname(root)
            try:
                metadata = obnamlib.read_metadata(self.fs, root)
            except OSError, e:
                logging.warning(
                    'Failed to get metadata for %s: %s: %s',
                    root, e.errno or 0, e.strerror)
                logging.warning('Using fake metadata instead for %s', root)
                metadata = dummy_metadata
            if not self.pretend:
                self.add_file_to_generation(root, metadata)

            if root == parent:
                break
            root = parent

    def backup_metadata(self, pathname, metadata):
        '''Back up metadata for a filesystem object'''

        tracing.trace('backup_metadata: %s', pathname)
        if not self.pretend:
            self.add_file_to_generation(pathname, metadata)

    def backup_file_contents(self, filename, metadata):
        '''Back up contents of a regular file.

        Sets the whole-file MD5 checksum in metadata as a side effect.

        '''

        tracing.trace('backup_file_contents: %s', filename)
        if self.pretend:
            tracing.trace('pretending to upload the whole file')
            self.progress.update_progress_with_upload(metadata.st_size)
            return

        tracing.trace('setting file chunks to empty')
        if not self.pretend:
            if self.repo.file_exists(self.new_generation, filename):
                self.repo.clear_file_chunk_ids(self.new_generation, filename)
            else:
                self.repo.add_file(self.new_generation, filename)

        tracing.trace('opening file for reading')
        f = self.fs.open(filename, 'r')

        checksum_key = self.repo.get_client_checksum_key(self.client_name)
        whole_file_summer = obnamlib.WholeFileCheckSummer(checksum_key)

        chunk_size = int(self.app.settings['chunk-size'])
        while True:
            tracing.trace('reading some data')
            self.progress.update_progress()
            data = f.read(chunk_size)
            if not data:
                tracing.trace('end of data')
                break
            tracing.trace('got %d bytes of data' % len(data))
            self.progress.update_progress_with_scanned(len(data))
            if not self.pretend:
                chunk_id = self.backup_file_chunk(data)
                self.repo.append_file_chunk_id(
                    self.new_generation, filename, chunk_id)
                whole_file_summer.append_chunk(data, chunk_id)
            else:
                self.progress.update_progress_with_upload(len(data))

            if not self.pretend:
                if self.checkpoint_manager.time_for_checkpoint():
                    logging.debug('making checkpoint in the middle of a file')
                    self.make_checkpoint()
                    self.progress.what(filename)

        tracing.trace('closing file')
        f.close()
        self.app.dump_memory_profile('at end of file content backup for %s' %
                                     filename)
        tracing.trace('done backing up file contents')

        for key, name in obnamlib.metadata_file_key_mapping:
            if key == checksum_key:
                setattr(metadata, name, whole_file_summer.get_checksum())

    def backup_file_chunk(self, data):
        '''Back up a chunk of data by putting it into the repository.'''

        def find():
            # We ignore lookup errors here intentionally. We're reading
            # the checksum trees without a lock, so another Obnam may be
            # modifying them, which can lead to spurious NodeMissing
            # exceptions, and other errors. We don't care: we'll just
            # pretend no chunk with the checksum exists yet.
            try:
                in_tree = self.repo.find_chunk_ids_by_token(token)
            except larch.Error:
                in_tree = []
            except obnamlib.RepositoryChunkContentNotInIndexes:
                in_tree = []
            return in_tree + self.chunkid_token_map.get(token)

        def get(chunkid):
            return self.repo.get_chunk_content(chunkid)

        def put():
            self.progress.update_progress_with_upload(len(data))
            return self.repo.put_chunk_content(data)

        def share(chunkid):
            self.chunkid_token_map.add(chunkid, token)

        token = self.repo.prepare_chunk_for_indexes(data)

        mode = self.app.settings['deduplicate']
        if mode == 'never':
            return put()
        elif mode == 'verify':
            for chunkid in find():
                data2 = get(chunkid)
                if data == data2:
                    share(chunkid)
                    return chunkid
            chunkid = put()
            share(chunkid)
            return chunkid
        elif mode == 'fatalist':
            existing = find()
            if existing:
                chunkid = existing[0]
            else:
                chunkid = put()
            share(chunkid)
            return chunkid
        else:
            if not hasattr(self, 'bad_deduplicate_reported'):
                logging.error('unknown --deduplicate setting value')
                self.bad_deduplicate_reported = True
            chunkid = put()
            share(chunkid)
            return chunkid

    def backup_dir_contents(self, root, no_delete_paths=None):
        '''Back up the list of files in a directory.

        'no_delete_paths' may contain an optional list of path names that
        should be ignored. Usually these should be other backup roots that are
        processed separately.
        '''

        tracing.trace('backup_dir: %s', root)
        if self.pretend:
            return

        if no_delete_paths is None:
            no_delete_paths = []

        new_basenames = self.fs.listdir(root)
        new_pathnames = [os.path.join(root, x) for x in new_basenames]
        if self.repo.file_exists(self.new_generation, root):
            old_pathnames = self.repo.get_file_children(
                self.new_generation, root)
        else:
            old_pathnames = []

        for old in old_pathnames:
            if old not in new_pathnames:
                self.repo.remove_file(self.new_generation, old)
            else:
                try:
                    st = self.fs.lstat(old)
                except OSError:
                    pass
                else:
                    # remove paths that were excluded recently
                    if (old not in no_delete_paths) and \
                            (not self.can_be_backed_up(old, st)):
                        self.repo.remove_file(self.new_generation, old)

        # Files that are created after the previous generation will be
        # added to the directory when they are backed up, so we don't
        # need to worry about them here.

    def remove_old_roots(self, new_roots):
        '''Remove from started generation anything that is not a backup root.

        We recurse from filesystem root directory until getting to one of
        the new backup roots, or a directory or file that is not a parent
        of one of the new backup roots. We remove anything that is not a
        new backup root, or their parent.

        '''

        def is_parent(pathname):
            if not pathname.endswith(os.sep):
                pathname += os.sep
            for new_root in new_roots:
                if new_root.startswith(pathname):
                    return True
            return False

        def helper(dirname):
            if dirname in new_roots:
                tracing.trace('is a new root: %s' % dirname)
            elif is_parent(dirname):
                tracing.trace('is parent of a new root: %s' % dirname)
                if self.repo.file_exists(gen_id, dirname):
                    pathnames = [
                        os.path.join(dirname, x)
                        for x in self.repo.get_file_children(gen_id, dirname)]
                    for pathname in pathnames:
                        helper(pathname)
            else:
                tracing.trace('is extra and removed: %s' % dirname)
                self.progress.what(
                    'removing %s from new generation' % dirname)
                self.repo.remove_file(self.new_generation, dirname)
                self.progress.what(msg)

        assert not self.pretend
        msg = 'removing old backup roots from new generation'
        self.progress.what(msg)
        tracing.trace('new_roots: %s' % repr(new_roots))
        gen_id = self.new_generation
        helper('/')
