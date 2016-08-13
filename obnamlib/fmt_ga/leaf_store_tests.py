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


# Pylint doesn't like the LeafStoreTests class, since its methods use
# attributes that aren't defined in the class (they're defined by the
# subclass). However, we know they'll be defined in time and also we
# want the test cases to be defined only once. So we silence pylint's
# no-member warning for this file.
#
# pylint: disable=no-member

class LeafStoreTests(object):

    def test_roundtrip_works(self):
        leaf = {'foo': 'bar'}
        leaf_id = self.ls.put_leaf(leaf)
        leaf2 = self.ls.get_leaf(leaf_id)
        self.assertEqual(leaf, leaf2)

    def test_returns_None_if_leaf_is_missing(self):
        self.assertEqual(self.ls.get_leaf(42), None)


class InMemoryLeafStoreTests(unittest.TestCase, LeafStoreTests):

    def setUp(self):
        self.ls = obnamlib.InMemoryLeafStore()
