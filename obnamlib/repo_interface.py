# repo_interface.py -- interface class for repository access
#
# Copyright 2013-2016  Lars Wirzenius
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
#
# =*= License: GPL-3+ =*=


import os
import stat
import unittest

import obnamlib


# The following is a canonical list of all keys that can be used with
# the repository interface for key/value pairs. Not all formats need
# to support all keys, but they all must support the test keys, for
# the test suite to function. All common file metadata keys must also
# be supported by all formats.
#
# The keys may change in value from run to run. Treat them as opaque,
# ephemeral things, and do not store them anywhere persistent.
#
# The symbols are meant to be used as Python symbols, but we do a
# little magic to get a) automatic enumeration b) mapping between
# values and names.


_saved_id = 0


def _get_next_id():
    global _saved_id
    _saved_id += 1
    return _saved_id


REPO_CLIENT_TEST_KEY = _get_next_id()
REPO_GENERATION_TEST_KEY = _get_next_id()
REPO_FILE_TEST_KEY = _get_next_id()
REPO_FILE_USERNAME = _get_next_id()
REPO_FILE_GROUPNAME = _get_next_id()
REPO_FILE_SYMLINK_TARGET = _get_next_id()
REPO_FILE_XATTR_BLOB = _get_next_id()
REPO_FILE_MD5 = _get_next_id()
REPO_FILE_SHA224 = _get_next_id()
REPO_FILE_SHA256 = _get_next_id()
REPO_FILE_SHA384 = _get_next_id()
REPO_FILE_SHA512 = _get_next_id()

_MAX_STRING_KEY = REPO_FILE_SHA512

REPO_GENERATION_STARTED = _get_next_id()
REPO_GENERATION_ENDED = _get_next_id()
REPO_GENERATION_IS_CHECKPOINT = _get_next_id()
REPO_GENERATION_FILE_COUNT = _get_next_id()
REPO_GENERATION_TOTAL_DATA = _get_next_id()
REPO_FILE_MODE = _get_next_id()
REPO_FILE_MTIME_SEC = _get_next_id()
REPO_FILE_MTIME_NSEC = _get_next_id()
REPO_FILE_ATIME_SEC = _get_next_id()
REPO_FILE_ATIME_NSEC = _get_next_id()
REPO_FILE_NLINK = _get_next_id()
REPO_FILE_SIZE = _get_next_id()
REPO_FILE_UID = _get_next_id()
REPO_FILE_GID = _get_next_id()
REPO_FILE_BLOCKS = _get_next_id()
REPO_FILE_DEV = _get_next_id()
REPO_FILE_INO = _get_next_id()


_repo_key_names = dict(
    (globals()[name], name)
    for name in globals()
    if name.startswith('REPO_'))


def _filter_integer_keys(prefix):
    return [
        globals()[name]
        for name in globals()
        if name.startswith(prefix) and globals()[name] > _MAX_STRING_KEY
    ]


REPO_GENERATION_INTEGER_KEYS = _filter_integer_keys('REPO_GENERATION_')
REPO_FILE_INTEGER_KEYS = _filter_integer_keys('REPO_FILE_')


def repo_key_name(key_value):
    return _repo_key_names.get(key_value, key_value)


# The following is a key that is NOT allowed for any repository format.

WRONG_KEY = -1


# A mapping between file keys and obnamlib.Metadata object fields.
metadata_file_key_mapping = [
    (REPO_FILE_MODE, 'st_mode'),
    (REPO_FILE_MTIME_SEC, 'st_mtime_sec'),
    (REPO_FILE_MTIME_NSEC, 'st_mtime_nsec'),
    (REPO_FILE_ATIME_SEC, 'st_atime_sec'),
    (REPO_FILE_ATIME_NSEC, 'st_atime_nsec'),
    (REPO_FILE_NLINK, 'st_nlink'),
    (REPO_FILE_SIZE, 'st_size'),
    (REPO_FILE_UID, 'st_uid'),
    (REPO_FILE_USERNAME, 'username'),
    (REPO_FILE_GID, 'st_gid'),
    (REPO_FILE_GROUPNAME, 'groupname'),
    (REPO_FILE_SYMLINK_TARGET, 'target'),
    (REPO_FILE_XATTR_BLOB, 'xattr'),
    (REPO_FILE_BLOCKS, 'st_blocks'),
    (REPO_FILE_DEV, 'st_dev'),
    (REPO_FILE_INO, 'st_ino'),
    (REPO_FILE_MD5, 'md5'),
    (REPO_FILE_SHA224, 'sha224'),
    (REPO_FILE_SHA256, 'sha256'),
    (REPO_FILE_SHA384, 'sha384'),
    (REPO_FILE_SHA512, 'sha512'),
]


class RepositoryClientListLockingFailed(obnamlib.ObnamError):

    msg = 'Repository client list could not be locked'


class RepositoryClientListNotLocked(obnamlib.ObnamError):

    msg = 'Repository client list is not locked'


class RepositoryClientAlreadyExists(obnamlib.ObnamError):

    msg = 'Repository client {client_name} already exists'


class RepositoryClientDoesNotExist(obnamlib.ObnamError):

    msg = 'Repository client {client_name} does not exist'


class RepositoryClientLockingFailed(obnamlib.ObnamError):

    msg = 'Repository client {client_name} could not be locked'


class RepositoryClientNotLocked(obnamlib.ObnamError):

    msg = 'Repository client {client_name} is not locked'


class RepositoryClientKeyNotAllowed(obnamlib.ObnamError):

    msg = (
        'Client {client_name} uses repository format {format} '
        'which does not allow the key {key_name} to be use for clients'
        )


class RepositoryClientGenerationUnfinished(obnamlib.ObnamError):

    msg = (
        'Cannot start new generation for {client_name}: '
        'previous one is not finished yet (programming error)'
        )


class RepositoryGenerationKeyNotAllowed(obnamlib.ObnamError):

    msg = (
        'Client {client_name} uses repository format {format} '
        'which does not allow the key {key_name} to be used for generations'
        )


class RepositoryGenerationDoesNotExist(obnamlib.ObnamError):

    msg = (
        'Cannot find requested generation {gen_id!r} '
        'for client {client_name}')


class RepositoryClientHasNoGenerations(obnamlib.ObnamError):

    msg = 'Client {client_name} has no generations'


class RepositoryFileDoesNotExistInGeneration(obnamlib.ObnamError):

    msg = (
        'Client {client_name}, generation {genspec} '
        'does not have file {filename}'
        )


class RepositoryFileKeyNotAllowed(obnamlib.ObnamError):

    msg = (
        'Client {client_name} uses repository format {format} '
        'which does not allow the key {key_name} to be use for files'
        )


class RepositoryChunkDoesNotExist(obnamlib.ObnamError):

    msg = (
        "Repository doesn't contain chunk {chunk_id}. "
        "It is expected at {filename}"
    )


class RepositoryChunkContentNotInIndexes(obnamlib.ObnamError):

    msg = "Repository chunk indexes do not contain content"


class RepositoryChunkIndexesNotLocked(obnamlib.ObnamError):

    msg = 'Repository chunk indexes are not locked'


class RepositoryChunkIndexesLockingFailed(obnamlib.ObnamError):

    msg = 'Repository chunk indexes are already locked'


class RepositoryInterface(object):

    '''Abstract interface to Obnam backup repositories.

    An Obnam backup repository stores backups for backup clients.
    As development of Obnam progresses, the details of how things
    are stored can change. This is usually necessary for performance
    improvements.

    To allow Obnam to access, both for reading and writing, any
    version of the repository format, this class defines an interface
    for repository access. Every different version of the format
    implements a class with this interface, so that the rest of
    Obnam can just use the interface.

    The interface is suitably high level that using the repository
    is convenient, and that it allows a variety of implementations.
    At the same time it concentrates on the needs of repository
    access only.

    The interface also specifies the interface with which the
    implementation accesses the actual filesystem: it is the
    Obnam VFS layer.

        [rest of Obnam code]
                |
                | calls RepositoryInterface API
                |
                V
        [RepositoryFormatX implementing RepositoryInterface API]
                |
                | calls VFS API
                |
                V
        [FooFS implementing VirtualFileSystem API]

    The VFS API implementation is given to the RepositoryInterface
    implementation with the ``set_fs`` method.

    It must be stressed that ALL access to the repository go via
    an implementation of RepositoryInterface. Further, all the
    implementation classes must be instantiated via RepositoryFactory.

    The abstraction RepositoryInterface provides for repositories
    consists of a few key concepts:

    * A repository contains data about one or more clients.
    * For each client, there is some metadata, plus a list of generations.
    * For each generation, there is some metadata, plus a list of
      files (where directories are treated as files).
    * For each file, there is some metadata, plus a list of chunk
      identifiers.
    * File contents data is split into chunks, each given a unique
      identifier.
    * There is optionally some indexing for content based lookups of
      chunks (e.g., look up chunks based on an MD5 checksum).
    * There are three levels of locking: the list of clients,
      the per-client data (information about generations), and
      the chunk lookup indexes are all locked up individually.
    * All metadata is stored as key/value pairs, where the key is one
      of a strictly limited, version-specific list of allowed ones,
      and the value is a binary string or a 64-bit integer (the type
      depends on the key). All allowed keys are implicitly set to
      the empty string or 0 if not set otherwise.

    Further, the repository format version implementation is given
    a directory in which it stores the repository, using any number
    of files it wishes. No other files will be in that directory.
    (RepositoryFactory creates the actual directory.) The only
    restriction is that within that directory, the
    ``metadata/format``file MUST be a plain text file (no encryption,
    compression), containing a single line, giving the format
    of the repository, as an arbitrary string. Each RepositoryInterface
    implementation will work with exactly one such format, and have
    a class attribute ``format`` which contains the string.

    There is no method to remove a repository. This is handled
    externally by removing the repository directory and all its files.
    Since that code is generic, it is not needed in the interface.

    Each RepositoryInterface implementation can have a custom
    initialiser. RepositoryFactory will know how to call it,
    giving it all the information it needs.

    Generation and chunk identifiers, as returned by this API, are
    opaque objects, which may be compared for equality, but not for
    sorting. A generation id will include information to identify
    the client it belongs to, in order to make it unnecessary to
    always specify the client.

    File metadata (stat fields, etc) are stored using individual
    file keys:

        repo.set_file_key(gen_id, filename, REPO_FILE_KEY_MTIME, mtime)

    This is to allow maximum flexibility in how data is actually stored
    in the repository, and to make the least amount of assumptions
    that will hinder convertability between repository formats.
    However, storing them independently is likely to be expensive,
    and so the implementation may actually pool file key changes to
    a file and only actually encode all of them, as a blob, when the
    API user is finished with a file. There is no API call to indicate
    that explicitly, but the API implementation can deduce it by noticing
    that another file's file key, or other metadata, gets set. This
    design aims to make the API as easy to use as possible, by avoiding
    an extra "I am finished with this file for now" method call.

    '''

    # Operations on the repository itself.

    @classmethod
    def setup_hooks(cls, hooks):  # pragma: no cover
        '''Create any hooks for this repository format.

        Note that this is a class method.

        Subclasses do not need to override this method, unless they
        need to add hooks.

        '''

        pass

    def get_fs(self):
        '''Get the Obnam VFS instance for accessing the filesystem.

        This is None, unless set by set_fs.

        '''

        raise NotImplementedError()

    def set_fs(self, fs):
        '''Set the Obnam VFS instance for accessing the filesystem.'''
        raise NotImplementedError()

    def init_repo(self):
        '''Initialize a nearly-empty directory for this format version.

        The repository will contain the file ``metadata/format``,
        with the right contents, but nothing else.

        '''

        raise NotImplementedError()

    def close(self):
        '''Close the repository and its filesystem.'''
        raise NotImplementedError()

    def get_shared_directories(self):
        '''Return list of directories for shared information in the repo.

        This is useful for some plugins that need to store extra data
        in each shared directory.

        '''
        raise NotImplementedError()

    # Global.

    def lock_everything(self):
        '''Lock every part of the repository.

        If the caller already holds a lock, that is kept. If anyone
        else holds a lock, the operation will fail. Ideally, the
        caller shouldn't hold a lock, since that may lead to a
        deadlock.

        '''
        unlockers = []
        gpg_unlockers = []
        try:
            if not self.got_client_list_lock():
                gpg_unlockers.append((self.unlock_client_list, []))
                self.lock_client_list()
                unlockers.append((self.unlock_client_list, []))

            for client_name in self.get_client_names():
                if not self.got_client_lock(client_name):
                    gpg_unlockers.append((self.unlock_client, [client_name]))
                    self.lock_client(client_name)
                    unlockers.append((self.unlock_client, [client_name]))

            if not self.got_chunk_indexes_lock():
                gpg_unlockers.append((self.unlock_chunk_indexes, []))
                self.lock_chunk_indexes()
        except obnamlib.LockFail:
            for unlocker, args in unlockers:
                unlocker(*args)
            raise
        except obnamlib.GpgError:
            for unlocker, args in gpg_unlockers:
                unlocker(*args)
            raise

    def unlock_everything(self):
        '''Unock every part of the repository to which we hold a lock.

        This also discards any changes made to each part made after
        the latest lock or commit of that part.

        '''

        if self.got_client_list_lock():
            self.unlock_client_list()

        for client_name in self.get_client_names():
            if self.got_client_lock(client_name):
                self.unlock_client(client_name)

        if self.got_chunk_indexes_lock():
            self.unlock_chunk_indexes()

    # Client list.

    def get_client_names(self):
        '''Return client names currently existing in the repository.'''
        raise NotImplementedError()

    def lock_client_list(self):
        '''Lock the client list for changes.'''
        raise NotImplementedError()

    def commit_client_list(self):
        '''Commit changes to client list and DO NOT unlock it.

        Note that the caller MUST also call unlock_client_list.
        Otherwise the client list remains locked.

        '''
        raise NotImplementedError()

    def unlock_client_list(self):
        '''Forget changes to client list and unlock it.

        The changes that are forgotten are those made after the latest
        lock_client_list or commit_client_list.

        '''
        raise NotImplementedError()

    def got_client_list_lock(self):
        '''Have we got the client list lock?'''
        raise NotImplementedError()

    def force_client_list_lock(self):
        '''Force the client list lock.

        If the process that locked the client list is dead, this
        method forces the lock open (removes the lock). Any
        uncommitted changes by the original locker will be lost.

        '''
        raise NotImplementedError()

    def add_client(self, client_name):
        '''Add a client to the client list.

        Raise RepositoryClientAlreadyExists if the client already exists.

        '''
        raise NotImplementedError()

    def remove_client(self, client_name):
        '''Remove a client from the client list.'''
        raise NotImplementedError()

    def rename_client(self, old_client_name, new_client_name):
        '''Rename a client to have a new name.'''
        raise NotImplementedError()

    def get_client_encryption_key_id(self, client_name):
        '''Return key id for the per-client encryption key.

        If client does not exist, raise RepositoryClientDoesNotExist.
        If client exists, but does not have an encryption key set,
        return None.

        '''
        raise NotImplementedError()

    def set_client_encryption_key_id(self, client_name, key_id):
        '''Set key id for the per-client encryption key.'''
        raise NotImplementedError()

    # A particular client.

    def client_is_locked(self, client_name):
        '''Is this client locked, possibly by someone else?'''
        raise NotImplementedError()

    def lock_client(self, client_name):
        '''Lock the client for changes.

        This lock must be taken for any changes to the per-client
        data, including any changes to backup generations for the
        client.

        '''
        raise NotImplementedError()

    def flush_client(self, client_name):
        '''Flush cached data from client. This is not a commit.

        This requires the client to be locked.

        This is a NOP, unless the a specific repository format gives
        it meaning.

        '''

    def flush_ro_client(self, client_name):
        '''Flush cached read-only data from client.

        This does not require the client to be locked.

        This is a NOP, unless the a specific repository format gives
        it meaning.

        '''

    def commit_client(self, client_name):
        '''Commit changes to client and DO NOT unlock it.

        Note that the caller MUST also call unlock_client. Otherwise
        the client list remains locked.

        '''
        raise NotImplementedError()

    def unlock_client(self, client_name):
        '''Forget changes to client and unlock it.

        The changes that are forgotten are those made after the latest
        lock_client or commit_client.

        '''
        raise NotImplementedError()

    def got_client_lock(self, client_name):
        '''Have we got the lock for a given client?'''
        raise NotImplementedError()

    def force_client_lock(self, client_name):
        '''Force the client lock.

        If the process that locked the client is dead, this method
        forces the lock open (removes the lock). Any uncommitted
        changes by the original locker will be lost.

        '''
        raise NotImplementedError()

    def get_allowed_client_keys(self):
        '''Return list of allowed per-client keys for thist format.'''
        raise NotImplementedError()

    def get_client_checksum_key(self, client_name):
        '''Return file key for preferred checksum for client, or None.'''
        raise NotImplementedError()

    def get_client_key(self, client_name, key):
        '''Return current value of a key for a given client.

        If not set explicitly, the value is the empty string.
        If the key is not in the list of allowed keys for this
        format, raise RepositoryClientKeyNotAllowed.

        '''
        raise NotImplementedError()

    def set_client_key(self, client_name, key, value):
        '''Set value for a per-client key.'''
        raise NotImplementedError()

    def get_client_generation_ids(self, client_name):
        '''Return a list of opaque ids for generations in a client.

        The list is ordered: the first id in the list is the oldest
        generation. The ids needs not be sortable, and they may or
        may not be simple types.

        '''
        raise NotImplementedError()

    def create_generation(self, client_name):
        '''Start a new generation for a client.

        Return the generation id for the new generation. The id
        implicitly also identifies the client.

        '''
        raise NotImplementedError()

    def get_client_extra_data_directory(self, client_name):
        '''Return directory for storing extra data for a client.

        Obnam plugins, for example, may need to store some per-client
        data that is specific to the plugin. This might be any kind of
        data, making it unsuitable for file keys (see get_file_key),
        which are suitable only for small bits of data.. The extra
        data might further need to be written in raw format. As an
        example, a hypothetical plugin might put the source code that
        of the Obnam version the client is using into the repository,
        to increase the chance that data can be restored even if only
        the repository remains. Or an encryption plugin might store
        encryption keys for the client here.

        This method returns the name of a directory, useable as-is
        with the VFS instance returned by the get_fs method.

        '''

        raise NotImplementedError()

    # Generations. The generation id identifies client as well.

    def get_allowed_generation_keys(self):
        '''Return list of all allowed keys for generations.'''
        raise NotImplementedError()

    def get_generation_key(self, generation_id, key):
        '''Return current value for a generation key.'''
        raise NotImplementedError()

    def set_generation_key(self, generation_id, key, value):
        '''Set a key/value pair for a given generation.'''
        raise NotImplementedError()

    def remove_generation(self, generation_id):
        '''Remove an existing generation.

        The removed generation may be the currently unfinished one.

        Return a list of chunk ids that are no longer used by this
        client.

        '''
        raise NotImplementedError()

    def get_generation_chunk_ids(self, generation_id):
        '''Return list of chunk ids used by a generation.

        Each file lists the chunks it uses, but iterating over all
        files is expensive. This method gives a potentially more
        efficient way of getting the information.

        '''
        raise NotImplementedError()

    def interpret_generation_spec(self, client_name, genspec):
        '''Return the generation id for a user-given specification.

        The specification is a string, and either gives the number
        of a generation, or is the word 'latest'.

        The return value is a generation id usable with the
        RepositoryInterface API.

        '''
        raise NotImplementedError()

    def make_generation_spec(self, gen_id):
        '''Return a generation spec that matches a given generation id.

        If we tell the user the returned string, and they later give
        it to interpret_generation_spec, the same generation id is
        returned.

        '''
        raise NotImplementedError()

    # Individual files and directories in a generation.

    def file_exists(self, generation_id, filename):
        '''Does a file exist in a generation?

        The filename should be the full path to the file.

        '''
        raise NotImplementedError()

    def add_file(self, generation_id, filename):
        '''Adds a file to the generation.

        Any metadata about the file needs to be added with
        set_file_key.

        '''
        raise NotImplementedError()

    def remove_file(self, generation_id, filename):
        '''Removes a file from the given generation.

        The generation MUST be the created, but not committed or
        unlocked generation.

        All the file keys associated with the file are also removed.

        '''
        raise NotImplementedError()

    def get_allowed_file_keys(self):
        '''Return list of allowed file keys for this format.'''
        raise NotImplementedError()

    def get_file_key(self, generation_id, filename, key):
        '''Return value for a file key, or empty string.

        The empty string is returned if no value has been set for the
        file key, or the file does not exist.

        '''
        raise NotImplementedError()

    def get_metadata_from_file_keys(self, generation_id, filename):
        '''Return a Metadata constructed from the file's keys.

        This is equivalent to creating the Metadata object and calling
        get_file_key for every allowed key and setting the
        corresponding field in the Metadata object. It may be faster
        on some repository formats, however.

        '''

        metadata = obnamlib.Metadata()

        allowed = set(self.get_allowed_file_keys())
        for key, field in obnamlib.metadata_file_key_mapping:
            if key in allowed:
                value = self.get_file_key(generation_id, filename, key)
                setattr(metadata, field, value)

        return metadata

    def set_file_key(self, generation_id, filename, key, value):

        '''Set value for a file key.

        It is an error to set the value for a file key if the file does
        not exist yet.

        '''
        raise NotImplementedError()

    def set_file_keys_from_metadata(self, generation_id, filename, metadata):
        '''Set all allowed file keys from obnamlib.Metadata.

        This is the same as calling set_file_key for each allowed key,
        but hopefully faster.

        '''

        allowed = set(self.get_allowed_file_keys())
        used = set()
        for key, field in obnamlib.metadata_file_key_mapping:
            if key in allowed:
                self.set_file_key(
                    generation_id, filename, key, getattr(metadata, field))
                used.add(key)

        for key in allowed.difference(used):
            self.set_file_key(generation_id, filename, key, None)

    def get_file_chunk_ids(self, generation_id, filename):
        '''Get the list of chunk ids for a file.'''
        raise NotImplementedError()

    def clear_file_chunk_ids(self, generation_id, filename):
        '''Clear the list of chunk ids for a file.'''
        raise NotImplementedError()

    def append_file_chunk_id(self, generation_id, filename, chunk_id):
        '''Add a chunk id for a file.

        The chunk id is added to the end of the list of chunk ids,
        so file data ordering is preserved..

        '''
        raise NotImplementedError()

    def get_file_children(self, generation_id, filename):
        '''List contents of a directory.

        This returns a list of full pathnames for all the files in
        the repository that are direct children of the given file.
        This may fail if the given file is not a directory, but
        that is not guaranteed.

        '''
        raise NotImplementedError()

    def walk_generation(self, gen_id, dirname):  # pragma: no cover
        '''Like os.walk, but for a generation.

        This is a generator. Each return value is a pathname.
        Directories are recursed into. If depth_first is set to
        Children of a directory are returned before the directory
        itself.

        Sub-classes do not need to define this method; the base
        class provides a generic implementation.

        '''

        arg = os.path.normpath(dirname)
        mode = self.get_file_key(gen_id, dirname, obnamlib.REPO_FILE_MODE)
        if stat.S_ISDIR(mode):
            kidpaths = self.get_file_children(gen_id, dirname)
            for kp in kidpaths:
                for x in self.walk_generation(gen_id, kp):
                    yield x
        yield arg

    # Chunks.

    def put_chunk_content(self, data):
        '''Add a new chunk into the repository.

        Return the chunk identifier.

        '''
        raise NotImplementedError()

    def get_chunk_content(self, chunk_id):
        '''Return the contents of a chunk, given its id.'''
        raise NotImplementedError()

    def has_chunk(self, chunk_id):
        '''Does a chunk (still) exist in the repository?'''
        raise NotImplementedError()

    def get_chunk_ids(self):
        '''Generate all chunk ids in repository.'''
        raise NotImplementedError()

    def flush_chunks(self):
        '''Write any pending new chunks to repository.'''
        raise NotImplementedError()

    def remove_unused_chunks(self):
        '''Remove chunks that are no longer used by any client.

        The caller MUST commit any changes to clients or chunk indexes
        before calling this method.

        '''
        raise NotImplementedError()

    def lock_chunk_indexes(self):
        '''Locks chunk indexes for updates.'''
        raise NotImplementedError()

    def unlock_chunk_indexes(self):
        '''Forget any changes to and and unlock chunk indexes.

        The changes that are forgotten are those made after the latest
        lock_chunk_indexes or commit_chunk_indexes.

        '''
        raise NotImplementedError()

    def got_chunk_indexes_lock(self):
        '''Have we got the chunk index lock?'''
        raise NotImplementedError()

    def force_chunk_indexes_lock(self):
        '''Forces a chunk index lock open.'''
        raise NotImplementedError()

    def commit_chunk_indexes(self):
        '''Commit changes to chunk indexes and DO NOT unlock it.

        Note that the caller MUST also call unlock_chunk_indexes.
        Otherwise the client list remains locked.

        '''
        raise NotImplementedError()

    def prepare_chunk_for_indexes(self, data):
        '''Prepare chunk for putting into indexes.

        Return a token to be given to put_chunk_into_indexes. The
        token is opaque: the caller may not interpret or use it in any
        way other than by giving it to put_chunk_into_indexes and for
        comparing tokens with each other. Two identical pieces of data
        will return identical tokens, and different pieces of data
        will probably return different tokens, but that is not
        guaranteed. No token is equal to None.

        The point of this is to allow the repository implementation
        to provide, say, a checksum that can be used instead of the
        whole data. This allows the caller to discard the data and
        do call put_chunk_into_indexes later, without excessive
        memory consumption. Also, the equality guarantees allow the
        caller to do de-duplication of chunks.

        '''

        raise NotImplementedError()

    def put_chunk_into_indexes(self, chunk_id, token, client_name):
        '''Adds a chunk to indexes using prepared token.

        The token must be one returned by prepare_chunk_for_indexes.

        This does not do any de-duplication.

        The indexes map a chunk id to its checksum, and a checksum
        to both the chunk ids (possibly several!) and the client ids
        for the clients that use the chunk. The client ids are used
        to track when a chunk is no longer used by anyone and can
        be removed.

        '''
        raise NotImplementedError()

    def remove_chunk_from_indexes(self, chunk_id, client_name):
        '''Removes a chunk from indexes, given its id, for a given client.'''
        raise NotImplementedError()

    def remove_chunk_from_indexes_for_all_clients(self, chunk_id):
        '''Removes a chunk from indexes, given its id, for all clients.'''
        raise NotImplementedError()

    def find_chunk_ids_by_token(self, token):
        '''Finds chunk ids that probably match a given content.

        The token must be a return value of prepare_chunk_for_indexes.

        This will raise RepositoryChunkContentNotInIndexes if the
        chunk is not in the indexes. Otherwise it will return all
        chunk ids that would have the same token (see
        prepare_chunk_for_indexes). Note that the chunks whose ids are
        returned do not necessarily match the given data; if the
        caller cares, they need to verify.

        '''
        raise NotImplementedError()

    def validate_chunk_content(self, chunk_id):
        '''Make sure the content of a chunk is valid.

        This is (presumably) done by storing a checksum of the chunk
        data in the chunk indexes, and then verifying that. However,
        it could be done by error checking codes. It could also not be
        done at all: if a repository format does not have chunk
        indexes in any form, it can just return None for all
        validation.

        If a chunk is missing, it should be treated as an invalid
        chunk (return False or None, depending).

        Return True if content is valid, False if it is invalid, and
        None if it is not known either way.

        '''

        raise NotImplementedError()

    # Fsck.

    def get_fsck_work_items(self):
        '''Returns fsck work items for checking this repository.

        This may be a generator or may return an iterable data
        structure.

        The returned work items are of type obnamlib.WorkItem. It may
        return further work items.

        '''
        raise NotImplementedError()


class RepositoryInterfaceTests(unittest.TestCase):  # pragma: no cover

    '''Tests for implementations of RepositoryInterface.

    Each implementation of RepositoryInterface should have a corresponding
    test class, which inherits this class. The test subclass must set
    ``self.repo`` to an instance of the class to be tested. The repository
    must be empty and uninitialised.

    '''

    # Tests for repository level things.

    repo = None

    def test_has_format_attribute(self):
        self.assertEqual(type(self.repo.format), str)

    def test_set_fs_sets_fs(self):
        self.repo.set_fs('foo')
        self.assertEqual(self.repo.get_fs(), 'foo')

    def test_closes_repository(self):
        # Can't think of a test to verify the closing happened,
        # so just calling the method will have to do for now.
        self.assertEqual(self.repo.close(), None)

    def test_returns_list_of_shared_directories(self):
        self.assertTrue(type(self.repo.get_shared_directories()), list)

    # Global locking.

    def test_has_no_client_lock_initially(self):
        self.setup_client()
        self.assertFalse(self.repo.client_is_locked('fooclient'))

    def test_locks_everything(self):
        self.setup_client()
        self.repo.lock_everything()
        self.assertTrue(self.repo.got_client_list_lock())
        self.assertTrue(self.repo.client_is_locked('fooclient'))
        self.assertTrue(self.repo.got_client_lock('fooclient'))
        self.assertTrue(self.repo.got_chunk_indexes_lock())

    def test_unlocks_everything(self):
        self.setup_client()
        self.repo.lock_everything()
        self.repo.unlock_everything()
        self.assertFalse(self.repo.got_client_list_lock())
        self.assertFalse(self.repo.client_is_locked('fooclient'))
        self.assertFalse(self.repo.got_client_lock('fooclient'))
        self.assertFalse(self.repo.got_chunk_indexes_lock())

    # Tests for the client list.

    def test_has_not_got_client_list_lock_initially(self):
        self.repo.init_repo()
        self.assertFalse(self.repo.got_client_list_lock())

    def test_got_client_list_lock_after_locking(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.assertTrue(self.repo.got_client_list_lock())

    def test_not_got_client_list_lock_after_unlocking(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.unlock_client_list()
        self.assertFalse(self.repo.got_client_list_lock())

    def test_has_no_clients_initially(self):
        self.repo.init_repo()
        self.assertEqual(self.repo.get_client_names(), [])

    def test_adds_a_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.assertEqual(self.repo.get_client_names(), ['foo'])

    def test_renames_a_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.repo.rename_client('foo', 'bar')
        self.assertEqual(self.repo.get_client_names(), ['bar'])

    def test_removes_a_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.remove_client('foo')
        self.assertEqual(self.repo.get_client_names(), [])

    def test_fails_adding_existing_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.assertRaises(
            obnamlib.RepositoryClientAlreadyExists,
            self.repo.add_client, 'foo')

    def test_fails_renaming_nonexistent_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.rename_client, 'foo', 'bar')

    def test_fails_renaming_to_existing_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.add_client('bar')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientAlreadyExists,
            self.repo.rename_client, 'foo', 'bar')

    def test_fails_removing_nonexistent_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.remove_client, 'foo')

    def test_raises_lock_error_if_adding_client_without_locking(self):
        self.repo.init_repo()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.add_client, 'foo')

    def test_raises_lock_error_if_renaming_client_without_locking(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.rename_client, 'foo', 'bar')

    def test_raises_lock_error_if_removing_client_without_locking(self):
        self.repo.init_repo()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.remove_client, 'foo')

    def test_unlocking_client_list_does_not_add_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.unlock_client_list()
        self.assertEqual(self.repo.get_client_names(), [])

    def test_unlocking_client_list_does_not_rename_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.repo.rename_client('foo', 'bar')
        self.repo.unlock_client_list()

        self.assertEqual(self.repo.get_client_names(), ['foo'])

    def test_unlocking_client_list_does_not_remove_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.repo.remove_client('foo')
        self.repo.unlock_client_list()

        self.assertEqual(self.repo.get_client_names(), ['foo'])

    def test_committing_client_list_adds_client(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()
        self.assertEqual(self.repo.get_client_names(), ['foo'])

    def test_committing_client_list_renames_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.repo.rename_client('foo', 'bar')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.assertEqual(self.repo.get_client_names(), ['bar'])

    def test_commiting_client_list_removes_client(self):
        self.repo.init_repo()

        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.repo.lock_client_list()
        self.repo.remove_client('foo')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

        self.assertEqual(self.repo.get_client_names(), [])

    def test_commiting_client_list_does_NOT_remove_lock(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.commit_client_list()
        self.assertTrue(self.repo.got_client_list_lock())

    def test_unlocking_client_list_removes_lock(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.unlock_client_list()
        self.assertFalse(self.repo.got_client_list_lock())

    def test_locking_client_list_twice_fails(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientListLockingFailed,
            self.repo.lock_client_list)

    def test_unlocking_client_list_when_unlocked_fails(self):
        self.repo.init_repo()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.unlock_client_list)

    def test_committing_client_list_when_unlocked_fails(self):
        self.repo.init_repo()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.commit_client_list)

    def test_forces_client_list_lock(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('bar')
        self.repo.force_client_list_lock()
        self.assertRaises(
            obnamlib.RepositoryClientListNotLocked,
            self.repo.add_client,
            'foo')
        self.repo.lock_client_list()
        self.assertEqual(self.repo.get_client_names(), [])

    def test_raises_error_when_getting_encryption_key_id_for_unknown(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.set_client_encryption_key_id, 'foo', 'keyid')

    def test_raises_error_when_setting_encryption_key_id_for_unknown(self):
        self.repo.init_repo()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.get_client_encryption_key_id, 'foo')

    def test_has_no_client_encryption_key_id_initially(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.assertEqual(
            self.repo.get_client_encryption_key_id('foo'),
            None)

    def test_sets_client_encryption_key_id(self):
        self.repo.init_repo()
        self.repo.lock_client_list()
        self.repo.add_client('foo')
        self.repo.set_client_encryption_key_id('foo', 'keyid')
        self.assertEqual(
            self.repo.get_client_encryption_key_id('foo'),
            'keyid')

    # Tests for client specific stuff.

    def setup_client(self):
        self.repo.lock_client_list()
        self.repo.add_client('fooclient')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

    def setup_two_clients(self):
        self.repo.lock_client_list()
        self.repo.add_client('fooclient')
        self.repo.add_client('barclient')
        self.repo.commit_client_list()
        self.repo.unlock_client_list()

    def test_have_not_got_client_lock_initially(self):
        self.setup_client()
        self.assertFalse(self.repo.got_client_lock('fooclient'))

    def test_got_client_lock_after_locking(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.assertTrue(self.repo.got_client_lock('fooclient'))

    def test_have_not_got_client_lock_after_unlocking(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertFalse(self.repo.got_client_lock('fooclient'))

    def test_locking_client_twice_fails(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.assertRaises(
            obnamlib.RepositoryClientLockingFailed,
            self.repo.lock_client, 'fooclient')

    def test_unlocking_client_when_unlocked_fails(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientNotLocked,
            self.repo.unlock_client, 'fooclient')

    def test_forcing_client_lock_works(self):
        self.setup_client()

        # Make sure client isn't locked. Then force the lock, lock it,
        # and force it again.
        self.assertFalse(self.repo.client_is_locked('fooclient'))
        self.repo.force_client_lock('fooclient')
        self.assertFalse(self.repo.client_is_locked('fooclient'))
        self.repo.lock_client('fooclient')
        self.assertTrue(self.repo.client_is_locked('fooclient'))
        self.repo.force_client_lock('fooclient')
        self.assertFalse(self.repo.client_is_locked('fooclient'))
        self.repo.lock_client('fooclient')
        self.assertTrue(self.repo.client_is_locked('fooclient'))

    def test_committing_client_when_unlocked_fails(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientNotLocked,
            self.repo.commit_client, 'fooclient')

    def test_unlocking_nonexistent_client_fails(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.unlock_client, 'notexist')

    def test_committing_nonexistent_client_fails(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientDoesNotExist,
            self.repo.commit_client, 'notexist')

    def test_committing_client_does_NOT_remove_lock(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.repo.commit_client('fooclient')
        self.assertTrue(self.repo.got_client_lock('fooclient'))

    def test_unlocking_client_removes_lock(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertFalse(self.repo.got_client_lock('fooclient'))

    def test_has_list_of_allowed_client_keys(self):
        self.assertEqual(type(self.repo.get_allowed_client_keys()), list)

    def test_gets_all_allowed_client_keys(self):
        self.setup_client()
        for key in self.repo.get_allowed_client_keys():
            value = self.repo.get_client_key('fooclient', key)
            self.assertEqual(type(value), str)

    def client_test_key_is_allowed(self):
        return (obnamlib.REPO_CLIENT_TEST_KEY in
                self.repo.get_allowed_client_keys())

    def test_has_empty_string_for_client_test_key(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            value = self.repo.get_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY)
            self.assertEqual(value, '')

    def test_sets_client_key(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            self.repo.lock_client('fooclient')
            self.repo.set_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY, 'bar')
            value = self.repo.get_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY)
            self.assertEqual(value, 'bar')

    def test_setting_disallowed_client_key_fails(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.assertRaises(
            obnamlib.RepositoryClientKeyNotAllowed,
            self.repo.set_client_key, 'fooclient', WRONG_KEY, '')

    def test_setting_client_key_without_locking_fails(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            self.assertRaises(
                obnamlib.RepositoryClientNotLocked,
                self.repo.set_client_key,
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY, 'bar')

    def test_committing_client_preserves_key_changes(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            self.repo.lock_client('fooclient')
            self.repo.set_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY, 'bar')
            value = self.repo.get_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY)
            self.repo.commit_client('fooclient')
            self.repo.unlock_client('fooclient')
            self.assertEqual(value, 'bar')

    def test_unlocking_client_undoes_key_changes(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            self.repo.lock_client('fooclient')
            self.repo.set_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY, 'bar')
            self.repo.unlock_client('fooclient')
            value = self.repo.get_client_key(
                'fooclient', obnamlib.REPO_CLIENT_TEST_KEY)
            self.assertEqual(value, '')

    def test_getting_client_key_for_unknown_client_fails(self):
        if self.client_test_key_is_allowed():
            self.setup_client()
            self.assertRaises(
                obnamlib.RepositoryClientDoesNotExist,
                self.repo.get_client_key, 'notexistclient',
                obnamlib.REPO_CLIENT_TEST_KEY)

    def test_new_client_has_no_generations(self):
        self.setup_client()
        self.assertEqual(self.repo.get_client_generation_ids('fooclient'), [])

    def test_creates_new_generation(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        new_id = self.repo.create_generation('fooclient')
        self.assertEqual(
            self.repo.get_client_generation_ids('fooclient'),
            [new_id])

    def test_creating_generation_fails_current_generation_unfinished(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.repo.create_generation('fooclient')
        self.assertRaises(
            obnamlib.RepositoryClientGenerationUnfinished,
            self.repo.create_generation, 'fooclient')

    def test_creating_generation_fails_if_client_is_unlocked(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientNotLocked,
            self.repo.create_generation, 'fooclient')

    def test_unlocking_client_removes_created_generation(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        self.repo.create_generation('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertEqual(self.repo.get_client_generation_ids('fooclient'), [])

    def test_committing_client_keeps_created_generation(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        new_id = self.repo.create_generation('fooclient')
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertEqual(
            self.repo.get_client_generation_ids('fooclient'),
            [new_id])

    def test_returns_directory_name_for_extra_data(self):
        self.setup_client()
        self.assertTrue(
            type(self.repo.get_client_extra_data_directory('fooclient')),
            str)

    # Operations on one generation.

    def create_generation(self):
        self.setup_client()
        self.repo.lock_client('fooclient')
        return self.repo.create_generation('fooclient')

    def generation_test_key_is_allowed(self):
        return (obnamlib.REPO_GENERATION_TEST_KEY in
                self.repo.get_allowed_generation_keys())

    def test_has_list_of_allowed_generation_keys(self):
        self.assertEqual(type(self.repo.get_allowed_generation_keys()), list)

    def test_gets_all_allowed_generation_keys(self):
        gen_id = self.create_generation()
        for key in self.repo.get_allowed_generation_keys():
            value = self.repo.get_generation_key(gen_id, key)
            self.assertTrue(
                isinstance(value, str) or
                isinstance(value, int))

    def test_has_empty_string_for_generation_test_key(self):
        if self.generation_test_key_is_allowed():
            gen_id = self.create_generation()
            value = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY)
            self.assertEqual(value, '')

    def test_sets_generation_key(self):
        if self.generation_test_key_is_allowed():
            gen_id = self.create_generation()
            self.repo.set_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY, 'bar')
            value = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY)
            self.assertEqual(value, 'bar')

    def test_setting_disallowed_generation_key_fails(self):
        if self.generation_test_key_is_allowed():
            gen_id = self.create_generation()
            self.assertRaises(
                obnamlib.RepositoryGenerationKeyNotAllowed,
                self.repo.set_generation_key, gen_id, WRONG_KEY, '')

    def test_setting_generation_key_without_locking_fails(self):
        if self.generation_test_key_is_allowed():
            gen_id = self.create_generation()
            self.repo.commit_client('fooclient')
            self.repo.unlock_client('fooclient')
            self.assertRaises(
                obnamlib.RepositoryClientNotLocked,
                self.repo.set_generation_key,
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY, 'bar')

    def test_committing_client_preserves_generation_key_changes(self):
        if self.generation_test_key_is_allowed():
            gen_id = self.create_generation()
            self.repo.set_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY, 'bar')
            value = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TEST_KEY)
            self.repo.commit_client('fooclient')
            self.repo.unlock_client('fooclient')
            self.assertEqual(value, 'bar')

    def test_removes_unfinished_generation(self):
        gen_id = self.create_generation()
        chunk_ids = self.repo.remove_generation(gen_id)
        self.assertEqual(self.repo.get_client_generation_ids('fooclient'), [])
        self.assertEqual(type(chunk_ids), list)

    def test_removes_finished_generation(self):
        gen_id = self.create_generation()
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.repo.lock_client('fooclient')
        chunk_ids = self.repo.remove_generation(gen_id)
        self.assertEqual(self.repo.get_client_generation_ids('fooclient'), [])
        self.assertEqual(type(chunk_ids), list)

    def test_removing_removed_generation_fails(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.remove_generation, gen_id)

    def test_removing_generation_without_client_lock_fails(self):
        gen_id = self.create_generation()
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertRaises(
            obnamlib.RepositoryClientNotLocked,
            self.repo.remove_generation, gen_id)

    def test_unlocking_client_forgets_generation_removal(self):
        gen_id = self.create_generation()
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.repo.lock_client('fooclient')
        self.repo.remove_generation(gen_id)
        self.repo.unlock_client('fooclient')
        self.assertEqual(
            self.repo.get_client_generation_ids('fooclient'),
            [gen_id])

    def test_committing_client_actually_removes_generation(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertEqual(self.repo.get_client_generation_ids('fooclient'), [])

    def test_empty_generation_uses_no_chunk_ids(self):
        gen_id = self.create_generation()
        self.assertEqual(self.repo.get_generation_chunk_ids(gen_id), [])

    def test_interprets_latest_as_a_generation_spec(self):
        gen_id = self.create_generation()
        self.assertEqual(
            self.repo.interpret_generation_spec('fooclient', 'latest'),
            gen_id)

    def test_interpreting_latest_genspec_without_generations_fails(self):
        self.setup_client()
        self.assertRaises(
            obnamlib.RepositoryClientHasNoGenerations,
            self.repo.interpret_generation_spec, 'fooclient', 'latest')

    def test_interprets_generation_spec(self):
        gen_id = self.create_generation()
        genspec = self.repo.make_generation_spec(gen_id)
        self.assertEqual(
            self.repo.interpret_generation_spec('fooclient', genspec),
            gen_id)

    def test_interpreting_generation_spec_for_removed_generation_fails(self):
        # Note that we must have at least one generation, after removing
        # one.
        gen_id = self.create_generation()
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.repo.lock_client('fooclient')
        self.repo.create_generation('fooclient')
        genspec = self.repo.make_generation_spec(gen_id)
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.interpret_generation_spec, 'fooclient', genspec)

    # Tests for individual files in a generation.

    def test_file_does_not_exist(self):
        gen_id = self.create_generation()
        self.assertFalse(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_adds_file(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_unlocking_forgets_file_add(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.unlock_client('fooclient')
        self.assertFalse(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_committing_remembers_file_add(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_creating_generation_clones_previous_one(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        gen_id_2 = self.repo.create_generation('fooclient')
        self.assertTrue(self.repo.file_exists(gen_id_2, '/foo/bar'))

    def test_removes_added_file_from_current_generation(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.remove_file(gen_id, '/foo/bar')
        self.assertFalse(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_unlocking_forgets_file_removal(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        self.repo.create_generation('fooclient')
        self.repo.remove_file(gen_id, '/foo/bar')
        self.repo.unlock_client('fooclient')

        self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_committing_remembers_file_removal(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        gen_id_2 = self.repo.create_generation('fooclient')
        self.assertTrue(self.repo.file_exists(gen_id_2, '/foo/bar'))
        self.repo.remove_file(gen_id_2, '/foo/bar')
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))
        self.assertFalse(self.repo.file_exists(gen_id_2, '/foo/bar'))

    def test_has_list_of_allowed_file_keys(self):
        self.assertEqual(type(self.repo.get_allowed_file_keys()), list)

    def test_all_common_file_metadata_keys_are_allowed(self):
        common = [
            REPO_FILE_MODE,
            REPO_FILE_MTIME_SEC,
            REPO_FILE_MTIME_NSEC,
            REPO_FILE_ATIME_SEC,
            REPO_FILE_ATIME_NSEC,
            REPO_FILE_NLINK,
            REPO_FILE_SIZE,
            REPO_FILE_UID,
            REPO_FILE_GID,
            REPO_FILE_BLOCKS,
            REPO_FILE_DEV,
            REPO_FILE_INO,
            REPO_FILE_USERNAME,
            REPO_FILE_GROUPNAME,
            REPO_FILE_SYMLINK_TARGET,
            REPO_FILE_XATTR_BLOB,
            ]
        for key in common:
            self.assertTrue(
                key in self.repo.get_allowed_file_keys(),
                'key %s (%d) not in allowed file keys' %
                (repo_key_name(key), key))

    def test_gets_all_allowed_file_keys(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        for key in self.repo.get_allowed_file_keys():
            value = self.repo.get_file_key(gen_id, '/foo/bar', key)
            if key in REPO_FILE_INTEGER_KEYS:
                self.assertEqual(
                    type(value), int,
                    msg='key %s (%d) has value %s which is not an int' %
                    (repo_key_name(key), key, repr(value)))
            else:
                self.assertEqual(
                    type(value), str,
                    msg='key %s (%d) has value %s which is not a str' %
                    (repo_key_name(key), key, repr(value)))

    def test_has_empty_string_for_file_test_key(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY)
        self.assertEqual(value, '')

    def test_get_file_key_fails_for_nonexistent_generation(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.get_file_key,
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY)

    def test_get_file_key_fails_for_forbidden_key(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.assertRaises(
            obnamlib.RepositoryFileKeyNotAllowed,
            self.repo.get_file_key,
            gen_id, '/foo/bar', WRONG_KEY)

    def test_get_file_key_fails_for_nonexistent_file(self):
        gen_id = self.create_generation()
        self.assertRaises(
            obnamlib.RepositoryFileDoesNotExistInGeneration,
            self.repo.get_file_key,
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY)

    def test_sets_file_key(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY, 'yoyo')
        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY)
        self.assertEqual(value, 'yoyo')

    def test_setting_disallowed_file_key_fails(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.assertRaises(
            obnamlib.RepositoryFileKeyNotAllowed,
            self.repo.set_file_key, gen_id, '/foo/bar', WRONG_KEY, 'yoyo')

    def test_file_has_zero_mtime_by_default(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC)
        self.assertEqual(value, 0)

    def test_sets_file_mtime(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC, 123)
        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC)
        self.assertEqual(value, 123)

    def test_set_file_key_fails_for_nonexistent_generation(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.set_file_key,
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY, 'yoyo')

    def test_setting_file_key_for_nonexistent_file_fails(self):
        gen_id = self.create_generation()
        self.assertRaises(
            obnamlib.RepositoryFileDoesNotExistInGeneration,
            self.repo.set_file_key,
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY, 'yoyo')

    # FIXME: These tests fails due to ClientMetadataTree brokenness, it seems.
    # They're disabled, for now. The bug is not exposed by existing code,
    # only by the new interface's tests.

    # def test_removing_file_removes_all_its_file_keys(self):
    #     gen_id = self.create_generation()
    #     self.repo.add_file(gen_id, '/foo/bar')
    #     self.repo.set_file_key(
    #         gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC, 123)

    #     # Remove the file. Key should be removed.
    #     self.repo.remove_file(gen_id, '/foo/bar')
    #     self.assertRaises(
    #         obnamlib.RepositoryFileDoesNotExistInGeneration,
    #         self.repo.get_file_key,
    #         gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC)

    #     # Add the file back. Key should still be removed.
    #     self.repo.add_file(gen_id, '/foo/bar')
    #     value = self.repo.get_file_key(
    #         gen_id, '/foo/bar', obnamlib.REPO_FILE_MTIME_SEC)
    #     self.assertEqual(value, 0)

    # def test_can_add_a_file_then_remove_then_add_it_again(self):
    #     gen_id = self.create_generation()

    #     self.repo.add_file(gen_id, '/foo/bar')
    #     self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))

    #     self.repo.remove_file(gen_id, '/foo/bar')
    #     self.assertFalse(self.repo.file_exists(gen_id, '/foo/bar'))

    #     self.repo.add_file(gen_id, '/foo/bar')
    #     self.assertTrue(self.repo.file_exists(gen_id, '/foo/bar'))

    def test_unlocking_client_forgets_set_file_keys(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY, 'yoyo')
        self.repo.unlock_client('fooclient')
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.get_file_key,
            gen_id, '/foo/bar', obnamlib.REPO_FILE_TEST_KEY)

    def test_committing_client_remembers_set_file_keys(self):
        # We use the symlink target for these tests, since the
        # FILE_TEST_KEY mightn't get stored.

        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET, 'yoyo')
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET)
        self.assertEqual(value, 'yoyo')

    def test_setting_file_key_does_not_affect_previous_generation(self):
        # We use the symlink target for these tests, since the
        # FILE_TEST_KEY mightn't get stored.

        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET, 'first')
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        gen_id_2 = self.repo.create_generation('fooclient')
        self.repo.set_file_key(
            gen_id_2, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET, 'second')
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        value = self.repo.get_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET)
        self.assertEqual(value, 'first')

        value_2 = self.repo.get_file_key(
            gen_id_2, '/foo/bar', obnamlib.REPO_FILE_SYMLINK_TARGET)
        self.assertEqual(value_2, 'second')

    def test_returns_an_acceptable_checksum_file_key_or_none(self):
        self.setup_client()
        self.assertTrue(
            self.repo.get_client_checksum_key('fooclient') in
            [None,
             obnamlib.REPO_FILE_MD5,
             obnamlib.REPO_FILE_SHA224,
             obnamlib.REPO_FILE_SHA256,
             obnamlib.REPO_FILE_SHA384,
             obnamlib.REPO_FILE_SHA512])

    def test_new_file_has_no_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.assertEqual(self.repo.get_file_chunk_ids(gen_id, '/foo/bar'), [])

    def test_getting_file_chunk_ids_for_nonexistent_generation_fails(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.get_file_chunk_ids, gen_id, '/foo/bar')

    def test_getting_file_chunk_ids_for_nonexistent_file_fails(self):
        gen_id = self.create_generation()
        self.assertRaises(
            obnamlib.RepositoryFileDoesNotExistInGeneration,
            self.repo.get_file_chunk_ids, gen_id, '/foo/bar')

    def test_appends_one_file_chunk_id(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id, '/foo/bar'),
            [1])

    def test_appends_two_file_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 2)
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id, '/foo/bar'),
            [1, 2])

    def test_appending_file_chunk_ids_in_nonexistent_generation_fails(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.append_file_chunk_id, gen_id, '/foo/bar', 1)

    def test_appending_file_chunk_ids_to_nonexistent_file_fails(self):
        gen_id = self.create_generation()
        self.assertRaises(
            obnamlib.RepositoryFileDoesNotExistInGeneration,
            self.repo.append_file_chunk_id, gen_id, '/foo/bar', 1)

    def test_adding_chunk_id_to_file_adds_it_to_generation_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.assertEqual(self.repo.get_generation_chunk_ids(gen_id), [1])

    def test_clears_file_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.repo.clear_file_chunk_ids(gen_id, '/foo/bar')
        self.assertEqual(self.repo.get_file_chunk_ids(gen_id, '/foo/bar'), [])

    def test_clearing_file_chunk_ids_in_nonexistent_generation_fails(self):
        gen_id = self.create_generation()
        self.repo.remove_generation(gen_id)
        self.assertRaises(
            obnamlib.RepositoryGenerationDoesNotExist,
            self.repo.clear_file_chunk_ids, gen_id, '/foo/bar')

    def test_clearing_file_chunk_ids_for_nonexistent_file_fails(self):
        gen_id = self.create_generation()
        self.assertRaises(
            obnamlib.RepositoryFileDoesNotExistInGeneration,
            self.repo.clear_file_chunk_ids, gen_id, '/foo/bar')

    def test_unlocking_client_forgets_modified_file_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        gen_id_2 = self.repo.create_generation('fooclient')
        self.repo.append_file_chunk_id(gen_id_2, '/foo/bar', 2)
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id_2, '/foo/bar'),
            [1, 2])

        self.repo.unlock_client('fooclient')
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id, '/foo/bar'),
            [1])

    def test_committing_child_remembers_modified_file_chunk_ids(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG)
        self.repo.append_file_chunk_id(gen_id, '/foo/bar', 1)
        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')

        self.repo.lock_client('fooclient')
        gen_id_2 = self.repo.create_generation('fooclient')
        self.repo.append_file_chunk_id(gen_id_2, '/foo/bar', 2)
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id_2, '/foo/bar'),
            [1, 2])

        self.repo.commit_client('fooclient')
        self.repo.unlock_client('fooclient')
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id, '/foo/bar'),
            [1])
        self.assertEqual(
            self.repo.get_file_chunk_ids(gen_id_2, '/foo/bar'),
            [1, 2])

    def test_new_file_has_no_children(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG | 0700)
        self.assertEqual(self.repo.get_file_children(gen_id, '/foo/bar'), [])

    def test_gets_file_child(self):
        gen_id = self.create_generation()

        self.repo.add_file(gen_id, '/foo')
        self.repo.set_file_key(
            gen_id, '/foo', obnamlib.REPO_FILE_MODE, stat.S_IFDIR | 0700)

        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFREG | 0700)

        self.assertEqual(
            self.repo.get_file_children(gen_id, '/foo'),
            ['/foo/bar'])

    def test_gets_only_immediate_child_for_file(self):
        gen_id = self.create_generation()
        self.repo.add_file(gen_id, '/')
        self.repo.set_file_key(
            gen_id, '/', obnamlib.REPO_FILE_MODE, stat.S_IFDIR | 0700)
        self.repo.add_file(gen_id, '/foo')
        self.repo.set_file_key(
            gen_id, '/foo', obnamlib.REPO_FILE_MODE, stat.S_IFDIR | 0700)
        self.repo.add_file(gen_id, '/foo/bar')
        self.repo.set_file_key(
            gen_id, '/foo/bar', obnamlib.REPO_FILE_MODE, stat.S_IFDIR | 0700)
        self.assertEqual(
            self.repo.get_file_children(gen_id, '/'),
            ['/foo'])

    # Chunk and chunk indexes.

    def test_puts_chunk_into_repository(self):
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.flush_chunks()
        self.assertTrue(self.repo.has_chunk(chunk_id))
        self.assertEqual(self.repo.get_chunk_content(chunk_id), 'foochunk')

    def test_finds_put_chunk_in_unflushed_repository(self):
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.assertTrue(self.repo.has_chunk(chunk_id))
        self.assertEqual(self.repo.get_chunk_content(chunk_id), 'foochunk')

    def test_get_chunk_ids_returns_nothing_initially(self):
        self.assertEqual(list(self.repo.get_chunk_ids()), [])

    def test_get_chunk_ids_returns_single_chunk(self):
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.assertEqual(list(self.repo.get_chunk_ids()), [chunk_id])

    def test_get_chunk_ids_returns_both_chunks(self):
        chunk_id_1 = self.repo.put_chunk_content('foochunk')
        chunk_id_2 = self.repo.put_chunk_content('otherchunk')
        self.assertEqual(
            set(self.repo.get_chunk_ids()),
            set([chunk_id_1, chunk_id_2]))

    def test_have_not_got_chunk_indexes_lock_initially(self):
        self.setup_client()
        self.assertFalse(self.repo.got_chunk_indexes_lock())

    def test_got_chunk_indexes_lock_after_locking(self):
        self.setup_client()
        self.repo.lock_chunk_indexes()
        self.assertTrue(self.repo.got_chunk_indexes_lock())

    def test_have_not_got_chunk_indexes_lock_after_unlocking(self):
        self.setup_client()
        self.repo.lock_chunk_indexes()
        self.repo.unlock_chunk_indexes()
        self.assertFalse(self.repo.got_chunk_indexes_lock())

    def test_adds_chunk_to_indexes(self):
        self.setup_client()
        self.repo.lock_chunk_indexes()
        chunk_id = self.repo.put_chunk_content('foochunk')
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.assertEqual(
            self.repo.find_chunk_ids_by_token(token), [chunk_id])

    def test_finds_all_matching_chunk_ids(self):
        self.setup_client()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.lock_chunk_indexes()

        chunk_id_1 = self.repo.put_chunk_content('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id_1, token, 'fooclient')

        chunk_id_2 = self.repo.put_chunk_content('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id_2, token, 'fooclient')

        self.assertEqual(
            set(self.repo.find_chunk_ids_by_token(token)),
            set([chunk_id_1, chunk_id_2]))

    def test_removes_chunk_from_indexes(self):
        self.setup_client()
        self.repo.lock_chunk_indexes()
        chunk_id = self.repo.put_chunk_content('foochunk')
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.remove_chunk_from_indexes(chunk_id, 'fooclient')
        self.assertRaises(
            obnamlib.RepositoryChunkContentNotInIndexes,
            self.repo.find_chunk_ids_by_token, token)

    def test_removes_chunk_from_indexes_for_all_clients(self):
        self.setup_two_clients()
        self.repo.lock_chunk_indexes()
        chunk_id = self.repo.put_chunk_content('foochunk')
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'barclient')
        self.repo.remove_chunk_from_indexes_for_all_clients(chunk_id)
        self.assertRaises(
            obnamlib.RepositoryChunkContentNotInIndexes,
            self.repo.find_chunk_ids_by_token, token)

    def test_putting_chunk_to_indexes_without_locking_them_fails(self):
        chunk_id = self.repo.put_chunk_content('foochunk')
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.assertRaises(
            obnamlib.RepositoryChunkIndexesNotLocked,
            self.repo.put_chunk_into_indexes,
            chunk_id, token, 'fooclient')

    def test_removing_chunk_from_indexes_without_locking_them_fails(self):
        self.setup_client()
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.lock_chunk_indexes()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.commit_chunk_indexes()
        self.repo.unlock_chunk_indexes()
        self.assertRaises(
            obnamlib.RepositoryChunkIndexesNotLocked,
            self.repo.remove_chunk_from_indexes, chunk_id, 'fooclient')

    def test_removing_chunk_from_all_clients_without_locking_them_fails(self):
        self.setup_client()
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.lock_chunk_indexes()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.commit_chunk_indexes()
        self.repo.unlock_chunk_indexes()
        self.assertRaises(
            obnamlib.RepositoryChunkIndexesNotLocked,
            self.repo.remove_chunk_from_indexes_for_all_clients, chunk_id)

    def test_unlocking_chunk_indexes_forgets_changes(self):
        self.setup_client()
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.lock_chunk_indexes()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.unlock_chunk_indexes()
        self.assertRaises(
            obnamlib.RepositoryChunkContentNotInIndexes,
            self.repo.find_chunk_ids_by_token, token)

    def test_committing_chunk_indexes_remembers_changes(self):
        self.setup_client()
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.lock_chunk_indexes()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.commit_chunk_indexes()
        self.repo.unlock_chunk_indexes()
        self.assertEqual(
            self.repo.find_chunk_ids_by_token(token), [chunk_id])

    def test_committing_does_NOT_remove_chunk_indexes_lock(self):
        self.repo.lock_chunk_indexes()
        self.repo.commit_chunk_indexes()
        self.assertTrue(self.repo.got_chunk_indexes_lock())

    def test_locking_chunk_indexes_twice_fails(self):
        self.repo.lock_chunk_indexes()
        self.assertRaises(
            obnamlib.RepositoryChunkIndexesLockingFailed,
            self.repo.lock_chunk_indexes)

    def test_unlocking_unlocked_chunk_indexes_fails(self):
        self.assertRaises(
            obnamlib.RepositoryChunkIndexesNotLocked,
            self.repo.unlock_chunk_indexes)

    def test_forces_chunk_index_lock(self):
        self.repo.lock_chunk_indexes()
        self.repo.force_chunk_indexes_lock()
        self.assertEqual(self.repo.lock_chunk_indexes(), None)

    def test_validate_chunk_content_returns_True_or_None(self):
        self.setup_client()
        chunk_id = self.repo.put_chunk_content('foochunk')
        self.repo.lock_chunk_indexes()
        token = self.repo.prepare_chunk_for_indexes('foochunk')
        self.repo.put_chunk_into_indexes(chunk_id, token, 'fooclient')
        self.repo.commit_chunk_indexes()
        self.repo.unlock_chunk_indexes()
        ret = self.repo.validate_chunk_content(chunk_id)
        self.assertTrue(ret is True or ret is None)

    # Fsck.

    def test_returns_fsck_work_item(self):
        for work in self.repo.get_fsck_work_items():
            self.assertNotEqual(work, None)
