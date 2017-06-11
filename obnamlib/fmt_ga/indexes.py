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


import os

import obnamlib


class GAChunkIndexes(object):

    _well_known_blob = 'root'

    def __init__(self):
        self._fs = None
        self._checksum_name = None
        self.set_dirname('chunk-indexes')
        self.clear()

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
        self._data_is_loaded = False
        self._by_chunk_id_tree = None
        self._by_checksum_tree = None
        self._used_by_tree = None

    def commit(self):
        self._load_data()
        self._save_data()

    def _save_data(self):
        root = {
            'checksum_algorithm': self._checksum_name,
            'by_chunk_id': self._by_chunk_id_tree.commit(),
            'by_checksum': self._by_checksum_tree.commit(),
            'used_by': self._used_by_tree.commit(),
        }

        blob = obnamlib.serialise_object(root)

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

            leaf_store = obnamlib.LeafStore()
            leaf_store.set_blob_store(blob_store)

            if blob is None:
                self._by_chunk_id_tree = self._empty_cowtree(leaf_store)
                self._by_checksum_tree = self._empty_cowtree(leaf_store)
                self._used_by_tree = self._empty_cowtree(leaf_store)
            else:
                data = obnamlib.deserialise_object(blob)
                self._checksum_name = data['checksum_algorithm']

                self._by_chunk_id_tree = self._load_cowtree(
                    leaf_store, data['by_chunk_id'])
                self._by_checksum_tree = self._load_cowtree(
                    leaf_store, data['by_checksum'])
                self._used_by_tree = self._load_cowtree(
                    leaf_store, data['used_by'])

            self._data_is_loaded = True

    def _empty_cowtree(self, leaf_store):
        cow = obnamlib.CowTree()
        cow.set_leaf_store(leaf_store)
        return cow

    def _load_cowtree(self, leaf_store, list_id):
        cow = self._empty_cowtree(leaf_store)
        cow.set_list_node(list_id)
        return cow

    def _get_filename(self):
        return os.path.join(self.get_dirname(), 'data.dat')

    def prepare_chunk_for_indexes(self, chunk_content):
        summer = obnamlib.get_checksum_algorithm(self._checksum_name)
        summer.update(chunk_content)
        return summer.hexdigest()

    def put_chunk_into_indexes(self, chunk_id, token, client_id):
        self._load_data()

        self._by_chunk_id_tree.insert(chunk_id, token)

        chunk_ids = self._by_checksum_tree.lookup(token)
        if chunk_ids is None:
            chunk_ids = [chunk_id]
        elif chunk_id not in chunk_ids:
            chunk_ids.append(chunk_id)
        self._by_checksum_tree.insert(token, chunk_ids)

        client_ids = self._used_by_tree.lookup(chunk_id)
        if client_ids is None:
            client_ids = [client_id]
        elif client_id not in client_ids:
            client_ids.append(client_id)
        self._used_by_tree.insert(chunk_id, client_ids)

    def find_chunk_ids_by_token(self, token):
        self._load_data()
        result = self._by_checksum_tree.lookup(token)
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
        client_ids = self._used_by_tree.lookup(chunk_id)
        if client_ids is not None and client_id in client_ids:
            client_ids.remove(client_id)
            self._used_by_tree.insert(chunk_id, client_ids)
            if client_ids:
                still_used = True
            else:
                # We leave an empty list, and use that in
                # remove_unused_chunks to indicate an unused chunk.
                pass
        return still_used

    def _remove_chunk_by_id(self, chunk_id):
        token = self._by_chunk_id_tree.lookup(chunk_id)
        if token is not None:
            # FIXME: Should we have CowTree.delete(key)?
            self._by_chunk_id_tree.insert(chunk_id, None)
        return token

    def _remove_chunk_by_checksum(self, chunk_id, token):
        chunk_ids = self._by_checksum_tree.lookup(token)
        if chunk_ids is not None and chunk_id in chunk_ids:
            chunk_ids.remove(chunk_id)
            self._by_checksum_tree.insert(token, chunk_ids)

    def _remove_all_used_by(self, chunk_id):
        self._used_by_tree.insert(chunk_id, None)

    def remove_unused_chunks(self, chunk_store):
        unused_chunks = self.get_unused_chunks)
        # FIXME: Drop unused chunks from all cowtreess

        maybe_unused_bags = self.get_bags_containing_chunks(
            chunk_store, unused_chunks)
        for bag_id in maybe_unused_bags:
            if not self.bag_is_used(bag_id):
                chunk_store.remove_bag(bag_id)

    def get_unused_chunks(self):
        return [
            chunk_id
            for chunk_id in self._used_by_tree.keys()
            if not self.is_chunk_used_by_anyone(chunk_id)
        ]

    def is_chunk_used_by_anyone(self, chunk_id):
        return self._used_by_tree(chunk_id) != []

    def get_bags_containing_chunks(self, chunk_store, chunk_ids):
        return set(
            chunk_id
            for chunk_id in chunk_ids
            chunk_store.get_bag_id(chunk_id)
        )

    def bag_is_used(self, chunk_ids):
        return any(
            self.is_chunk_used_by_anyone(chunk_id)
            for chunk_id in chunk_ids
        )

    def validate_chunk_content(self, chunk_id):
        return None
