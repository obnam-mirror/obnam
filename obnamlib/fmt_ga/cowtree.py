# Copyright 2016-2017  Lars Wirzenius
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


class CowTree(object):

    def __init__(self):
        self._store = None
        self._leaf_list = obnamlib.LeafList()
        self._delta = obnamlib.CowDelta()
        self._max_keys_per_leaf = 1024  # FIXME: This should be configurable?

    def set_leaf_store(self, leaf_store):
        self._store = leaf_store

    def set_list_node(self, leaf_id):
        fake_leaf = self._store.get_leaf(leaf_id)
        serialised = fake_leaf.lookup('leaf_list')
        self._leaf_list = obnamlib.LeafList.unserialise(serialised)

    def set_max_leaf_size(self, max_keys):
        assert max_keys >= 2
        self._max_keys_per_leaf = max_keys

    def lookup(self, key):
        if key in self._delta:
            value = self._delta.get(key)
            if value is obnamlib.removed_key:
                return None
            return value

        leaf_id = self._leaf_list.find_leaf(key)
        if leaf_id is None:
            return None

        leaf = self._store.get_leaf(leaf_id)
        assert leaf is not None
        return leaf.lookup(key)

    def insert(self, key, value):
        self._delta.set(key, value)

    def remove(self, key):
        self._delta.remove(key)

    def keys(self):
        delta_keys = set(self._delta.keys())
        for key in delta_keys:
            if self._delta.get(key) != obnamlib.removed_key:
                yield key

        leaf_ids = self._leaf_list.leaves()
        for leaf_id in leaf_ids:
            leaf = self._store.get_leaf(leaf_id)
            for key in leaf.keys():
                if key not in delta_keys:
                    yield key

    def commit(self):
        keys = sorted(self.keys())
        leaf = obnamlib.CowLeaf()
        leaf_list = obnamlib.LeafList()
        for key in keys:
            assert len(leaf) < self._max_keys_per_leaf
            leaf.insert(key, self.lookup(key))
            if len(leaf) == self._max_keys_per_leaf:
                self._add_leaf(leaf_list, leaf)
                leaf = obnamlib.CowLeaf()
        if len(leaf) > 0:
            self._add_leaf(leaf_list, leaf)
        leaf_id = self._put_leaf_list(leaf_list)
        self._remove_old_tree(self._leaf_list)
        return leaf_id

    def _add_leaf(self, leaf_list, leaf):
        leaf_id = self._store.put_leaf(leaf)
        keys = leaf.keys()
        leaf_list.add(leaf_id, keys[0], keys[-1])

    def _put_leaf_list(self, leaf_list):
        fake_leaf = obnamlib.CowLeaf()
        fake_leaf.insert('leaf_list', leaf_list.serialise())
        list_id = self._store.put_leaf(fake_leaf)
        self._store.flush()
        return list_id

    def _remove_old_tree(self, leaf_list):  # pragma: no cover
        for leaf_id in leaf_list.leaves():
            self._store.remove_leaf(leaf_id)
