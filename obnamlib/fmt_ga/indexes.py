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


import errno
import logging
import os

import obnamlib


class GAChunkIndexes(object):

    _well_known_blob = 'root'

    def __init__(self):
        obnamlib.object_created(self)
        self._fs = None
        self._checksum_name = None
        self.set_dirname('chunk-indexes')
        self.clear()

    def __del__(self):
        obnamlib.object_deleted(self, self._data)

    def set_fs(self, fs):
        self._fs = fs

        # Load the data so that we can get the in-use checksum
        # algorithm at once, before we use the default, just in case
        # they're different.
        self._load_data()

    def set_default_checksum_algorithm(self, name):
        if self._checksum_name is None:
            self._checksum_name = name

    def set_dirname(self, dirname):
        self._dirname = dirname

    def get_dirname(self):
        return self._dirname

    def clear(self):
        self._data = {}
        self._data_is_loaded = False

    def commit(self):
        self._load_data()
        self._save_data()

    def _save_data(self):
        blob = obnamlib.serialise_object(self._data)

        bag_store = obnamlib.BagStore()
        bag_store.set_location(self._fs, self.get_dirname())

        blob_store = obnamlib.BlobStore()
        blob_store.set_bag_store(bag_store)
        blob_store.put_well_known_blob(self._well_known_blob, blob)

    def _load_data(self):
        if not self._data_is_loaded:
            bag_store = obnamlib.BagStore()
            bag_store.set_location(self._fs, self.get_dirname())

            blob_store = obnamlib.BlobStore()
            blob_store.set_bag_store(bag_store)
            blob = blob_store.get_well_known_blob(self._well_known_blob)

            if blob is None:
                self._data = {
                    'by_chunk_id': {
                    },
                    'by_checksum': {
                        self._checksum_name: {},
                    },
                    'used_by': {
                    },
                }
            else:
                self._data = obnamlib.deserialise_object(blob)
                assert self._data is not None

                keys = self._data['by_checksum'].keys()
                assert len(keys) == 1
                self._checksum_name = keys[0]

            self._data_is_loaded = True

    def _get_filename(self):
        return os.path.join(self.get_dirname(), 'data.dat')

    def prepare_chunk_for_indexes(self, chunk_content):
        summer = obnamlib.get_checksum_algorithm(self._checksum_name)
        summer.update(chunk_content)
        return summer.hexdigest()

    def put_chunk_into_indexes(self, chunk_id, token, client_id):
        self._load_data()

        by_chunk_id = self._data['by_chunk_id']
        by_chunk_id[chunk_id] = token

        by_checksum = self._data['by_checksum'][self._checksum_name]
        chunk_ids = by_checksum.get(token, [])
        if chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)
            by_checksum[token] = chunk_ids

        used_by = self._data['used_by']
        client_ids = used_by.get(chunk_id, [])
        if client_id not in client_ids:
            client_ids.append(client_id)
            used_by[chunk_id] = client_ids

    def find_chunk_ids_by_token(self, token):
        self._load_data()

        by_checksum = self._data['by_checksum'][self._checksum_name]
        result = by_checksum.get(token, [])

        if not result:
            raise obnamlib.RepositoryChunkContentNotInIndexes()
        return result

    def remove_chunk_from_indexes(self, chunk_id, client_id):
        self._load_data()
        if not self._remove_used_by(chunk_id, client_id):
            token = self._remove_chunk_by_id(chunk_id)
            self._remove_chunk_by_checksum(chunk_id, token)

    def remove_chunk_from_indexes_for_all_clients(self, chunk_id):
        self._load_data()
        token = self._remove_chunk_by_id(chunk_id)
        self._remove_chunk_by_checksum(chunk_id, token)
        self._remove_all_used_by(chunk_id)

    def _remove_used_by(self, chunk_id, client_id):
        still_used = False
        used_by = self._data['used_by']
        client_ids = used_by.get(chunk_id, [])
        if client_id in client_ids:
            client_ids.remove(client_id)
            if client_ids:
                still_used = True
            else:
                # We leave an empty here, and use that in
                # remove_unused_chunks to indicate an unused chunk.
                pass
        return still_used

    def _remove_chunk_by_id(self, chunk_id):
        by_chunk_id = self._data['by_chunk_id']
        token = by_chunk_id.get(chunk_id, None)
        if token is not None:
            del by_chunk_id[chunk_id]
        return token

    def _remove_chunk_by_checksum(self, chunk_id, token):
        by_checksum = self._data['by_checksum'][self._checksum_name]
        chunk_ids = by_checksum.get(token, [])
        if chunk_id in chunk_ids:
            chunk_ids.remove(chunk_id)
            if not chunk_ids:
                del by_checksum[token]

    def _remove_all_used_by(self, chunk_id):
        used_by = self._data['used_by']
        if chunk_id in used_by:
            del used_by[chunk_id]

    def remove_unused_chunks(self, chunk_store):

        def find_ids_of_unused_chunks(used_by):
            return set(x for x in used_by if not used_by[x])

        def remove_from_used_by(used_by, chunk_ids):
            for chunk_id in chunk_ids:
                del used_by[chunk_id]

        def get_bag_ids(chunk_ids):
            return set(
                obnamlib.parse_object_id(chunk_id)[0]
                for chunk_id in chunks_to_remove)

        def get_chunk_ids_in_bag(bag_id):
            bag = chunk_store._bag_store.get_bag(bag_id)
            return [
                obnamlib.make_object_id(bag_id, i)
                for i in range(len(bag))
            ]

        def remove_bag_if_unused(used_by, bag_id):
            chunk_ids = get_chunk_ids_in_bag(bag_id)
            if not any(chunk_id in used_by for chunk_id in chunk_ids):
                chunk_store._bag_store.remove_bag(bag_id)

        self._load_data()
        used_by = self._data['used_by']
        chunks_to_remove = find_ids_of_unused_chunks(used_by)
        remove_from_used_by(used_by, chunks_to_remove)
        for bag_id in get_bag_ids(chunks_to_remove):
            try:
                remove_bag_if_unused(used_by, bag_id)
            except EnvironmentError as e:
                if e.errno == errno.ENOENT:
                    # The bag's missing. We log, but otherwise
                    # ignore that. Don't want to crash a forget
                    # operation just because a chunk that was
                    # meant to be removed is already removed.
                    logging.warning(
                        'Tried to delete bag that was missing: %s', bag_id)
                else:
                    raise

    def validate_chunk_content(self, chunk_id):
        return None
