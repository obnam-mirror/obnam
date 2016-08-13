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


import obnamlib


class CowTree(object):

    def __init__(self):
        self._store = None
        self._leaf = obnamlib.CowLeaf()

    def set_leaf_store(self, leaf_store):
        self._store = leaf_store

    def set_list_node(self, leaf_id):
        self._leaf = self._store.get_leaf(leaf_id)

    def lookup(self, key):
        return self._leaf.lookup(key)

    def insert(self, key, value):
        self._leaf.insert(key, value)

    def commit(self):
        return self._store.put_leaf(self._leaf)
