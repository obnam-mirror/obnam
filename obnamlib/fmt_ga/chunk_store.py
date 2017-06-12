# Copyright 2015  Lars Wirzenius
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


class GAChunkStore(object):

    def __init__(self):
        self._fs = None
        self._dirname = 'chunk-store'
        self._max_chunk_size = None
        self._chunk_cache_size = obnamlib.DEFAULT_CHUNK_CACHE_BYTES
        self._bag_store = None
        self._blob_store = None

    def set_fs(self, fs):
        self._fs = fs

        self._bag_store = obnamlib.BagStore()
        self._bag_store.set_location(fs, self._dirname)
        self._blob_store = obnamlib.BlobStore()
        self._blob_store.set_bag_store(self._bag_store)
        self._blob_store.set_max_cache_bytes(self._chunk_cache_size)
        if self._max_chunk_size is not None:
            self._blob_store.set_max_bag_size(self._max_chunk_size)

    def set_max_chunk_size(self, max_chunk_size):
        self._max_chunk_size = max_chunk_size
        if self._blob_store:
            self._blob_store.set_max_bag_size(max_chunk_size)

    def set_chunk_cache_size(self, chunk_cache_size):
        self._chunk_cache_size = chunk_cache_size
        if self._blob_store:
            self._blob_store.set_max_cache_bytes(chunk_cache_size)

    def put_chunk_content(self, content):
        self._fs.create_and_init_toplevel(self._dirname)
        return self._blob_store.put_blob(content)

    def flush_chunks(self):
        self._blob_store.flush()

    def get_chunk_content(self, chunk_id):
        content = self._blob_store.get_blob(chunk_id)
        if content is None:
            raise obnamlib.RepositoryChunkDoesNotExist(
                chunk_id=chunk_id,
                filename=None)
        return content

    def get_bag_id(self, chunk_id):
        bag_id, _ = obnamlib.parse_object_id(chunk_id)
        return bag_id

    def get_chunks_in_bag(self, bag_id):
        try:
            bag = self._bag_store.get_bag(bag_id)
        except EnvironmentError:
            pass
        else:
            for i in range(len(bag)):
                yield obnamlib.make_object_id(bag_id, i)

    def remove_bag(self, bag_id):
        try:
            self._bag_store.remove_bag(bag_id)
        except EnvironmentError:
            pass

    def has_chunk(self, chunk_id):
        # This is ugly, 'cause it requires reading in the whole bag.
        # We could easily check if the bag exists, but not whether it
        # contains the actual chunk.
        try:
            return self.get_chunk_content(chunk_id)
        except obnamlib.RepositoryChunkDoesNotExist:
            return False
        else:
            return True

    def get_chunk_ids(self):
        # This is slow as hell, as it needs to read in all the bags to
        # get all the chunk ids. We're going to need to either drop
        # get_chunk_ids or have a way to get the blob identifiers for
        # a bag without reading it in and parsing it.

        self.flush_chunks()
        result = []
        for bag_id in self._bag_store.get_bag_ids():
            bag = self._bag_store.get_bag(bag_id)
            result += self._get_chunk_ids_from_bag(bag)
        return result

    def _get_chunk_ids_from_bag(self, bag):
        return [obnamlib.make_object_id(bag.get_id(), i)
                for i in range(len(bag))]
