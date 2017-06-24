# Copyright 2017  Lars Wirzenius
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


class LeafListTests(unittest.TestCase):

    def test_is_empty_initially(self):
        ll = obnamlib.LeafList()
        self.assertEqual(len(ll), 0)

    def test_adds_leaf(self):
        first_key = 'aaaa'
        last_key = 'bbbb'
        leaf_id = 'leaf-1'

        ll = obnamlib.LeafList()
        ll.add(leaf_id, first_key, last_key)
        self.assertEqual(len(ll), 1)
        self.assertEqual(ll.leaves(), [leaf_id])

    def test_adding_overlapping_leaf_raises_exception(self):
        first_key = 'a'
        last_key = 'b'
        leaf_id_1 = 'leaf-1'
        leaf_id_2 = 'leaf-2'

        ll = obnamlib.LeafList()
        ll.add(leaf_id_1, first_key, last_key)

        with self.assertRaises(Exception):
            ll.add(leaf_id_2, first_key, last_key)

    def test_adds_second_leaf(self):
        leaf1 = ('leaf-1', 'a', 'b')
        leaf2 = ('leaf-2', 'c', 'd')

        ll = obnamlib.LeafList()
        # Note that we insert in reverse order to make sure .add puts things
        # into the right order.
        ll.add(*leaf2)
        ll.add(*leaf1)

        self.assertEqual(len(ll), 2)
        self.assertEqual(ll.leaves(), [leaf1[0], leaf2[0]])

    def test_adds_third_leaf_in_the_middle(self):
        leaf1 = ('leaf-1', 'a', 'b')
        leaf2 = ('leaf-2', 'e', 'f')
        leaf3 = ('leaf-2', 'c', 'd')

        ll = obnamlib.LeafList()
        ll.add(*leaf1)
        ll.add(*leaf3)
        ll.add(*leaf2)

        self.assertEqual(len(ll), 3)
        self.assertEqual(ll.leaves(), [leaf1[0], leaf2[0], leaf3[0]])

    def test_finds_correct_leaf(self):
        leaf1 = ('leaf-1', 'a', 'b')
        leaf2 = ('leaf-2', 'c', 'd')
        leaf3 = ('leaf-3', 'e', 'f')

        ll = obnamlib.LeafList()
        ll.add(*leaf1)
        ll.add(*leaf3)
        ll.add(*leaf2)

        found = ll.find_leaf('aaa')
        self.assertNotEqual(found, None)
        self.assertEqual(found, leaf1[0])

    def test_finds_none(self):
        leaf1 = ('leaf-1', 'a', 'b')
        leaf2 = ('leaf-2', 'c', 'd')
        leaf3 = ('leaf-3', 'e', 'f')

        ll = obnamlib.LeafList()
        ll.add(*leaf1)
        ll.add(*leaf3)
        ll.add(*leaf2)

        found = ll.find_leaf('z')
        self.assertEqual(found, None)

    def test_serialisation_roundtrip(self):
        leaf1 = ('leaf-1', 'a', 'b')
        leaf2 = ('leaf-2', 'c', 'd')
        leaf3 = ('leaf-3', 'e', 'f')

        orig = obnamlib.LeafList()
        orig.add(*leaf1)
        orig.add(*leaf3)
        orig.add(*leaf2)

        serialised = orig.serialise()
        new = obnamlib.LeafList.unserialise(serialised)

        self.assertEqual(orig.leaves(), new.leaves())
