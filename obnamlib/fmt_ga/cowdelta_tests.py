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


class CowDeltaTests(unittest.TestCase):

    def test_is_empty_initially(self):
        delta = obnamlib.CowDelta()
        self.assertEqual(delta.keys(), [])
        self.assertFalse('key' in delta)

    def test_remembers_key_value_pair(self):
        delta = obnamlib.CowDelta()
        delta.set('key', 'value')
        self.assertEqual(delta.keys(), ['key'])
        self.assertEqual(delta.get('key'), 'value')
        self.assertTrue('key' in delta)

    def test_remembers_second_value_for_key(self):
        delta = obnamlib.CowDelta()
        delta.set('key', 'old-value')
        delta.set('key', 'new-value')
        self.assertEqual(delta.keys(), ['key'])
        self.assertEqual(delta.get('key'), 'new-value')
        self.assertTrue('key' in delta)

    def test_remembers_removed_key(self):
        delta = obnamlib.CowDelta()
        delta.remove('key')
        self.assertEqual(delta.keys(), ['key'])
        self.assertEqual(delta.get('key'), obnamlib.removed_key)
        self.assertTrue('key' in delta)
