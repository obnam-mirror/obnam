# Copyright 2015-2016  Lars Wirzenius
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


import obnamlib


class RepositoryDelegator(obnamlib.RepositoryInterface):

    '''Implement RepositoryInterface by delegating to other objects.'''

    format = None

    def __init__(self, **kwargs):
        self._fs = None
        self._hooks = kwargs['hooks']
        self._lock_timeout = kwargs.get('lock_timeout', 0)
        self._lockmgr = None

        self._client_list = None
        self._chunk_store = None
        self._chunk_indexes = None

        self._client_finder = ClientFinder()
        self._client_finder.set_current_time(kwargs['current_time'])
        self._client_finder.set_dir_bag_size(kwargs['dir_bag_size'])
        self._client_finder.set_dir_cache_size(kwargs['dir_cache_size'])

    def set_client_list_object(self, client_list):
        self._client_list = client_list
        self._client_finder.set_client_list(self._client_list)

    def set_chunk_store_object(self, chunk_store):
        self._chunk_store = chunk_store

    def set_chunk_indexes_object(self, chunk_indexes):
        self._chunk_indexes = chunk_indexes

    def set_client_factory(self, client_factory):
        self._client_finder.set_client_factory(client_factory)

    def get_fs(self):
        return self._fs.fs

    def set_fs(self, fs):
        self._fs = obnamlib.RepositoryFS(self, fs, self._hooks)
        self._lockmgr = obnamlib.LockManager(self._fs, self._lock_timeout, '')

        self._client_list.set_fs(self._fs)
        self._client_list.set_hooks(self._hooks)
        self._client_finder.set_fs(self._fs)
        self._chunk_store.set_fs(self._fs)
        self._chunk_indexes.set_fs(self._fs)

    #
    # Repository methods.
    #

    def init_repo(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    #
    # Client list methods.
    #

    def get_client_names(self):
        return list(self._client_list.get_client_names())

    def lock_client_list(self):
        self._require_we_have_not_locked_client_list()
        dirname = self._client_list.get_dirname()
        self._fs.create_and_init_toplevel(dirname)
        self._lockmgr.lock([dirname])
        self._client_list.clear()

    def _require_we_have_not_locked_client_list(self):
        dirname = self._client_list.get_dirname()
        if self._lockmgr.got_lock(dirname):
            raise obnamlib.RepositoryClientListLockingFailed()

    def unlock_client_list(self):
        self._require_we_got_client_list_lock()
        self._client_list.clear()
        dirname = self._client_list.get_dirname()
        self._lockmgr.unlock([dirname])

    def _require_we_got_client_list_lock(self):
        if not self.got_client_list_lock():
            raise obnamlib.RepositoryClientListNotLocked()

    def commit_client_list(self):
        self._require_we_got_client_list_lock()
        self._client_list.commit()

    def got_client_list_lock(self):
        dirname = self._client_list.get_dirname()
        return self._lockmgr.got_lock(dirname)

    def force_client_list_lock(self):
        dirname = self._client_list.get_dirname()
        self._lockmgr.force([dirname])
        self._client_list.clear()

    def add_client(self, client_name):
        self._require_we_got_client_list_lock()
        self._client_list.add_client(client_name)

    def remove_client(self, client_name):
        self._require_we_got_client_list_lock()
        self._client_list.remove_client(client_name)
        self._client_finder.remove_client(client_name)

    def rename_client(self, old_client_name, new_client_name):
        self._require_we_got_client_list_lock()
        self._client_list.rename_client(old_client_name, new_client_name)

    def get_client_encryption_key_id(self, client_name):
        return self._client_list.get_client_encryption_key_id(client_name)

    def set_client_encryption_key_id(self, client_name, key_id):
        self._require_we_got_client_list_lock()
        return self._client_list.set_client_encryption_key_id(
            client_name, key_id)

    #
    # Per-client methods.
    #

    def client_is_locked(self, client_name):
        client = self._lookup_client(client_name)
        return self._lockmgr.is_locked(client.get_dirname())

    def _lookup_client(self, client_name):
        return self._client_finder.find_client(client_name)

    def lock_client(self, client_name):
        self._require_we_have_not_locked_client(client_name)
        client = self._lookup_client(client_name)
        dirname = client.get_dirname()
        self._fs.create_and_init_toplevel(dirname)
        self._lockmgr.lock([dirname])
        client.clear()

    def _require_we_have_not_locked_client(self, client_name):
        client = self._lookup_client(client_name)
        if self._lockmgr.got_lock(client.get_dirname()):
            raise obnamlib.RepositoryClientLockingFailed()

    def unlock_client(self, client_name):
        self._require_got_client_lock(client_name)
        client = self._lookup_client(client_name)
        client.clear()
        self._lockmgr.unlock([client.get_dirname()])

    def _require_got_client_lock(self, client_name):
        if not self.got_client_lock(client_name):
            raise obnamlib.RepositoryClientNotLocked(client_name=client_name)

    def flush_client(self, client_name):
        self._require_got_client_lock(client_name)
        client = self._lookup_client(client_name)
        client.flush()

    def commit_client(self, client_name):
        self._require_got_client_lock(client_name)
        client = self._lookup_client(client_name)
        client.commit()

    def got_client_lock(self, client_name):
        client = self._lookup_client(client_name)
        return self._lockmgr.got_lock(client.get_dirname())

    def force_client_lock(self, client_name):
        client = self._lookup_client(client_name)
        self._lockmgr.force([client.get_dirname()])
        client.clear()

    def get_client_generation_ids(self, client_name):
        return self._lookup_client(client_name).get_client_generation_ids()

    def create_generation(self, client_name):
        self._require_got_client_lock(client_name)
        return self._lookup_client(client_name).create_generation()

    def get_generation_key(self, generation_id, key):
        client = self._lookup_client_by_generation(generation_id)
        return client.get_generation_key(generation_id.gen_number, key)

    def _lookup_client_by_generation(self, generation_id):
        return self._lookup_client(generation_id.client_name)

    def set_generation_key(self, generation_id, key, value):
        if key not in self.get_allowed_generation_keys():
            raise obnamlib.RepositoryGenerationKeyNotAllowed(
                client_name=generation_id.client_name,
                format=self.format,
                key_name=obnamlib.repo_key_name(key))
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.set_generation_key(generation_id.gen_number, key, value)

    def remove_generation(self, generation_id):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.remove_generation(generation_id.gen_number)

    def get_generation_chunk_ids(self, generation_id):
        client = self._lookup_client_by_generation(generation_id)
        return client.get_generation_chunk_ids(generation_id.gen_number)

    def file_exists(self, generation_id, filename):
        client = self._lookup_client_by_generation(generation_id)
        return client.file_exists(generation_id.gen_number, filename)

    def add_file(self, generation_id, filename):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.add_file(generation_id.gen_number, filename)

    def remove_file(self, generation_id, filename):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.remove_file(generation_id.gen_number, filename)

    def get_metadata_from_file_keys(self, generation_id, filename):
        client = self._lookup_client_by_generation(generation_id)
        return client.get_metadata_from_file_keys(
            generation_id.gen_number, filename)

    def get_file_key(self, generation_id, filename, key):
        if key not in self.get_allowed_file_keys():
            raise obnamlib.RepositoryFileKeyNotAllowed(
                client_name=generation_id.client_name,
                key_name=obnamlib.repo_key_name(key),
                format=self.format)

        client = self._lookup_client_by_generation(generation_id)
        return client.get_file_key(generation_id.gen_number, filename, key)

    def set_file_key(self, generation_id, filename, key, value):
        if key not in self.get_allowed_file_keys():
            raise obnamlib.RepositoryFileKeyNotAllowed(
                client_name=generation_id.client_name,
                key_name=obnamlib.repo_key_name(key),
                format=self.format)

        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.set_file_key(
            generation_id.gen_number, filename, key, value)

    def set_file_keys_from_metadata(self, generation_id, filename, metadata):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.set_file_keys_from_metadata(
            generation_id.gen_number, filename, metadata)

    def get_client_checksum_key(self, client_name):
        client = self._lookup_client(client_name)
        return client.get_client_checksum_key()

    def get_file_chunk_ids(self, generation_id, filename):
        client = self._lookup_client_by_generation(generation_id)
        return client.get_file_chunk_ids(generation_id.gen_number, filename)

    def append_file_chunk_id(self, generation_id, filename, chunk_id):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.append_file_chunk_id(
            generation_id.gen_number, filename, chunk_id)

    def clear_file_chunk_ids(self, generation_id, filename):
        self._require_got_client_lock(generation_id.client_name)
        client = self._lookup_client_by_generation(generation_id)
        return client.clear_file_chunk_ids(generation_id.gen_number, filename)

    def get_file_children(self, generation_id, filename):
        client = self._lookup_client_by_generation(generation_id)
        return client.get_file_children(generation_id.gen_number, filename)

    #
    # Chunk storage methods.
    #

    def put_chunk_content(self, content):
        return self._chunk_store.put_chunk_content(content)

    def get_chunk_content(self, chunk_id):
        return self._chunk_store.get_chunk_content(chunk_id)

    def has_chunk(self, chunk_id):
        return self._chunk_store.has_chunk(chunk_id)

    def flush_chunks(self):
        self._chunk_store.flush_chunks()

    def get_chunk_ids(self):
        return self._chunk_store.get_chunk_ids()

    #
    # Chunk indexes methods.
    #

    def lock_chunk_indexes(self):
        self._require_we_have_not_locked_chunk_indexes()
        dirname = self._chunk_indexes.get_dirname()
        self._fs.create_and_init_toplevel(dirname)
        self._lockmgr.lock([dirname])
        self._chunk_indexes.clear()

    def _require_we_have_not_locked_chunk_indexes(self):
        if self.got_chunk_indexes_lock():
            raise obnamlib.RepositoryChunkIndexesLockingFailed()

    def unlock_chunk_indexes(self):
        self._require_we_got_chunk_indexes_lock()
        self._chunk_indexes.clear()
        dirname = self._chunk_indexes.get_dirname()
        self._lockmgr.unlock([dirname])

    def _require_we_got_chunk_indexes_lock(self):
        if not self.got_chunk_indexes_lock():
            raise obnamlib.RepositoryChunkIndexesNotLocked()

    def commit_chunk_indexes(self):
        self._require_we_got_chunk_indexes_lock()
        self._chunk_indexes.commit()

    def got_chunk_indexes_lock(self):
        dirname = self._chunk_indexes.get_dirname()
        return self._lockmgr.got_lock(dirname)

    def force_chunk_indexes_lock(self):
        dirname = self._chunk_indexes.get_dirname()
        self._lockmgr.force([dirname])
        self._chunk_indexes.clear()

    def prepare_chunk_for_indexes(self, chunk_content):
        return self._chunk_indexes.prepare_chunk_for_indexes(chunk_content)

    def put_chunk_into_indexes(self, chunk_id, token, client_id):
        self._require_we_got_chunk_indexes_lock()
        return self._chunk_indexes.put_chunk_into_indexes(
            chunk_id, token, client_id)

    def find_chunk_ids_by_token(self, token):
        return self._chunk_indexes.find_chunk_ids_by_token(token)

    def remove_chunk_from_indexes(self, chunk_id, client_id):
        self._require_we_got_chunk_indexes_lock()
        self._chunk_indexes.remove_chunk_from_indexes(chunk_id, client_id)

    def remove_chunk_from_indexes_for_all_clients(self, chunk_id):
        self._require_we_got_chunk_indexes_lock()
        self._chunk_indexes.remove_chunk_from_indexes_for_all_clients(chunk_id)

    def remove_unused_chunks(self):
        self._require_we_got_chunk_indexes_lock()
        # Note that we need to give remove_unused_chunks the chunk
        # store as an argument, so that it can actually remove chunks.
        return self._chunk_indexes.remove_unused_chunks(self._chunk_store)

    def validate_chunk_content(self, chunk_id):
        return self._chunk_indexes.validate_chunk_content(chunk_id)


class ClientFinder(object):

    def __init__(self):
        self._client_factory = None
        self._fs = None
        self._client_list = None
        self._clients = {}
        self._current_time = None
        self._dir_bag_size = None
        self._dir_cache_size = None

    def set_client_factory(self, client_factory):
        self._client_factory = client_factory

    def set_fs(self, fs):
        self._fs = fs

    def set_client_list(self, client_list):
        self._client_list = client_list

    def set_current_time(self, current_time):
        self._current_time = current_time

    def set_dir_bag_size(self, size):
        self._dir_bag_size = size

    def set_dir_cache_size(self, size):
        self._dir_cache_size = size

    def find_client(self, client_name):
        if client_name not in self._clients:
            if client_name not in self._client_list.get_client_names():
                raise obnamlib.RepositoryClientDoesNotExist(
                    client_name=client_name)

            client = self._client_factory(client_name)
            client.set_fs(self._fs)
            dirname = self._client_list.get_client_dirname(client_name)
            client.set_dirname(dirname)
            client.set_current_time(self._current_time)
            client.set_dir_cache_size(self._dir_cache_size)
            client.set_dir_bag_size(self._dir_bag_size)
            self._clients[client_name] = client

        return self._clients[client_name]

    def remove_client(self, client_name):
        if client_name in self._clients:
            del self._clients[client_name]


class GenerationId(object):

    def __init__(self, client_name, gen_number):
        self.client_name = client_name
        self.gen_number = gen_number

    def __eq__(self, other):
        return (other is not None and
                self.client_name == other.client_name and
                self.gen_number == other.gen_number)

    def __str__(self):  # pragma: no cover
        return '%s:%s' % (self.client_name, self.gen_number)

    def __repr__(self):  # pragma: no cover
        return 'GenerationId(%s,%s)' % (self.client_name, self.gen_number)
