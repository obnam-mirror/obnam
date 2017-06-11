# Copyright 2016  Lars Wirzenius
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


import copy

import obnamlib


class CowTree(object):

    def __init__(self):
        self._store = None
        self._leaf_list = _LeafList()
        self._max_keys_per_leaf = 1024  # FIXME: This should be configurable?

    def set_leaf_store(self, leaf_store):
        self._store = leaf_store

    def set_list_node(self, leaf_id):
        fake_leaf = self._store.get_leaf(leaf_id)
        self._leaf_list.from_dict(fake_leaf.lookup('leaf_list'))

    def set_max_leaf_size(self, max_keys):
        assert max_keys >= 2
        self._max_keys_per_leaf = max_keys

    def lookup(self, key):
        leaf_id = self._leaf_list.find_leaf_for_key(key)
        if leaf_id is None:
            return None

        leaf = self._store.get_leaf(leaf_id)
        assert leaf is not None
        return leaf.lookup(key)

    def insert(self, key, value):
        leaf_id = self._leaf_list.find_leaf_for_key(key)
        if leaf_id is None:
            self._add_new_leaf(key, value)
        else:
            self._insert_into_leaf(leaf_id, key, value)

    def _add_new_leaf(self, key, value):
        leaf = obnamlib.CowLeaf()
        leaf.insert(key, value)
        leaf_id = self._store.put_leaf(leaf)
        self._leaf_list.insert_leaf(key, key, leaf_id)

    def _insert_into_leaf(self, leaf_id, key, value):
        leaf = self._store.get_leaf(leaf_id)
        assert leaf is not None
        leaf.insert(key, value)
        keys = list(sorted(leaf.keys()))
        self._leaf_list.update_leaf(leaf_id, keys[0], keys[-1])
        if len(leaf) > self._max_keys_per_leaf:
            self._leaf_list.drop_leaf(leaf_id)
            self._split_leaf(leaf)

    def _split_leaf(self, leaf):
        sorted_keys = list(sorted(leaf.keys()))
        n = len(sorted_keys) / 2

        self._make_split_leaf(leaf, sorted_keys[:n])
        self._make_split_leaf(leaf, sorted_keys[n:])

    def _make_split_leaf(self, leaf, sorted_keys):
        new = obnamlib.CowLeaf()
        for key in sorted_keys:
            new.insert(key, leaf.lookup(key))
        new_id = self._store.put_leaf(new)
        self._leaf_list.insert_leaf(sorted_keys[0], sorted_keys[-1], new_id)

    def keys(self):
        for leaf_id in self._leaf_list.leaf_ids():
            leaf = self._store.get_leaf(leaf_id)
            for key in leaf.keys():
                yield key

    def commit(self):
        fake_leaf = obnamlib.CowLeaf()
        fake_leaf.insert('leaf_list', self._leaf_list.as_dict())
        list_id = self._store.put_leaf(fake_leaf)
        self._store.flush()
        return list_id


class _LeafList(object):

    def __init__(self):
        self._leaf_list = []

    def as_dict(self):
        # This isn't really returning a dict, but that's OK. We only
        # need to return something that serialise_object can handle.
        return copy.deepcopy(self._leaf_list)

    def from_dict(self, some_dict):
        self._leaf_list = some_dict

    def leaf_ids(self):
        for leaf_info in self._leaf_list:
            yield leaf_info['id']

    def find_leaf_for_key(self, key):
        # If there are no leaves, we can't pick one for key.
        if not self._leaf_list:
            return None

        # Pick last one if key is too big.
        last = self._leaf_list[-1]
        if key >= last['last_key']:
            return last['id']

        # Otherwise, pick first leaf whose last key >= key. We now
        # know there is such a node.
        for leaf_info in self._leaf_list:
            if leaf_info['last_key'] >= key:
                return leaf_info['id']

        # If we get here, something's badly wrong.
        assert False  # pragma: no cover

    def insert_leaf(self, first_key, last_key, leaf_id):
        leaf_info = {
            'first_key': first_key,
            'last_key': last_key,
            'id': leaf_id,
        }

        self._leaf_list.append(leaf_info)
        self._leaf_list.sort(key=lambda li: li['first_key'])

    def update_leaf(self, leaf_id, first_key, last_key):
        for leaf_info in self._leaf_list:
            if leaf_info['id'] == leaf_id:
                leaf_info['first_key'] = first_key
                leaf_info['last_key'] = last_key

    def drop_leaf(self, leaf_id):
        self._leaf_list = [
            leaf_info
            for leaf_info in self._leaf_list
            if leaf_info['id'] != leaf_id
        ]
