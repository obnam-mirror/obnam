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


import unittest

import obnamlib


class CowTreeTests(unittest.TestCase):

    def setUp(self):
        self.ls = obnamlib.InMemoryLeafStore()
        self.cow = obnamlib.CowTree()
        self.cow.set_leaf_store(self.ls)

    def test_lookup_returns_none_if_key_is_missing(self):
        self.assertEqual(self.cow.lookup(42), None)

    def test_returns_keyvalue_that_has_been_inserted(self):
        key = 'fookey'
        value = 'barvalue'
        self.cow.insert(key, value)
        self.assertEqual(self.cow.lookup(key), value)

    def test_commits_changes_persistently(self):
        key = 'fookey'
        value = 'barvalue'
        self.cow.insert(key, value)
        list_id = self.cow.commit()

        cow2 = obnamlib.CowTree()
        cow2.set_leaf_store(self.ls)
        cow2.set_list_node(list_id)
        self.assertEqual(cow2.lookup(key), value)
