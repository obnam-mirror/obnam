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


class CowLeafTests(unittest.TestCase):

    def test_has_zero_length_initially(self):
        leaf = obnamlib.CowLeaf()
        self.assertEqual(len(leaf), 0)

    def test_has_no_keys_initially(self):
        leaf = obnamlib.CowLeaf()
        self.assertEqual(leaf.keys(), [])

    def test_lookup_returns_None_if_key_is_missing(self):
        leaf = obnamlib.CowLeaf()
        self.assertEqual(leaf.lookup(42), None)

    def test_lookup_returns_inserted_value(self):
        key = 'fookey'
        value = 'barvalue'
        leaf = obnamlib.CowLeaf()
        leaf.insert(key, value)
        self.assertEqual(leaf.lookup(key), value)

    def test_inserting_increases_length(self):
        leaf = obnamlib.CowLeaf()
        leaf.insert('foo', 'bar')
        self.assertEqual(len(leaf), 1)

    def test_inserting_adds_key(self):
        leaf = obnamlib.CowLeaf()
        leaf.insert('foo', 'bar')
        self.assertEqual(leaf.keys(), ['foo'])

    def test_dict_round_trip(self):
        leaf = obnamlib.CowLeaf()
        leaf.insert('foo', 'bar')
        some_dict = leaf.as_dict()

        leaf2 = obnamlib.CowLeaf()
        leaf2.from_dict(some_dict)
        some_dict2 = leaf2.as_dict()

        self.assertNotEqual(id(some_dict), id(some_dict2))
        self.assertEqual(some_dict, some_dict2)
