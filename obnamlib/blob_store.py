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


class BlobStore(object):

    def __init__(self):
        self._bag_store = None
        self._bag = None
        self._max_bag_size = 0
        self._cached_blobs = BlobCache()
        self._cached_blobs.set_max_bytes(2**24)

    def set_bag_store(self, bag_store):
        self._bag_store = bag_store

    def set_max_bag_size(self, max_bag_size):
        self._max_bag_size = max_bag_size

    def set_max_cache_bytes(self, max_bytes):  # pragma: no cover
        self._cached_blobs.set_max_bytes(max_bytes)

    def get_blob(self, blob_id):
        bag_id, index = obnamlib.parse_object_id(blob_id)
        if self._bag and bag_id == self._bag.get_id():
            return self._bag[index]
        if blob_id in self._cached_blobs:
            return self._cached_blobs.get(blob_id)
        if self._bag_store.has_bag(bag_id):
            bag = self._bag_store.get_bag(bag_id)
            for i, this_blob in enumerate(bag):
                this_id = obnamlib.make_object_id(bag_id, i)
                self._cached_blobs.put(this_id, this_blob)
            return bag[index]
        return None

    def put_blob(self, blob):
        if self._bag is None:
            self._bag = self._new_bag()
        blob_id = self._bag.append(blob)
        if self._bag.get_bytes() >= self._max_bag_size:
            self.flush()
        return blob_id

    def _new_bag(self):
        bag = obnamlib.Bag()
        bag.set_id(self._bag_store.reserve_bag_id())
        return bag

    def get_well_known_blob(self, well_known_name):
        if self._bag_store.has_bag(well_known_name):
            bag = self._bag_store.get_bag(well_known_name)
            if len(bag) > 0:
                return bag[0]
        return None

    def put_well_known_blob(self, well_known_name, blob):
        bag = obnamlib.Bag()
        bag.set_id(well_known_name)
        bag.append(blob)
        self._bag_store.put_bag(bag)

    def flush(self):
        if self._bag is not None:
            self._bag_store.put_bag(self._bag)
            self._bag = None


class BlobCache(object):

    def __init__(self):
        obnamlib.object_created(self)
        self._max_bytes = None
        self._clear()

    def __del__(self):
        obnamlib.object_deleted(self, self._cache)

    def _clear(self):
        self._cache = {}
        self._cache_size = 0

    def set_max_bytes(self, max_bytes):
        self._max_bytes = max_bytes

    def put(self, blob_id, blob):
        if self._cache_size + len(blob) > self._max_bytes:  # pragma: no cover
            self._clear()
        self._cache[blob_id] = blob
        self._cache_size += len(blob)

    def get(self, blob_id):
        return self._cache[blob_id]

    def __contains__(self, blob_id):
        return blob_id in self._cache
