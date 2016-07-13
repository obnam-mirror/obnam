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


import stat
import unittest

import obnamlib


class GADirectoryTests(unittest.TestCase):

    def test_is_mutable_initially(self):
        dir_obj = obnamlib.GADirectory()
        self.assertTrue(dir_obj.is_mutable())

    def test_can_be_made_immutable(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.set_immutable()
        self.assertFalse(dir_obj.is_mutable())

    def test_returns_itself_as_dictionary(self):
        dir_obj = obnamlib.GADirectory()
        self.assertEqual(type(dir_obj.as_dict()), dict)

    def test_has_no_files_initially(self):
        dir_obj = obnamlib.GADirectory()
        self.assertEqual(dir_obj.get_file_basenames(), [])

    def test_adds_file(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        self.assertEqual(dir_obj.get_file_basenames(), ['README'])

    def test_raises_error_if_immutable_and_file_is_added(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.add_file, 'README')

    def test_removes_file(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.remove_file('README')
        self.assertEqual(dir_obj.get_file_basenames(), [])

    def test_removes_nonexistent_file(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.remove_file('README')
        self.assertEqual(dir_obj.get_file_basenames(), [])

    def test_raises_error_if_immutable_and_file_is_removed(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.remove_file, 'README')

    def test_maps_file_key_to_short_name_and_back(self):
        key = obnamlib.REPO_FILE_SIZE

        dir_obj = obnamlib.GADirectory()
        short = dir_obj.get_short_key_name(key)
        key2 = dir_obj.get_key_from_short_name(short)
        self.assertEqual(key, key2)

    def test_gets_file_key_when_unset(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        self.assertEqual(
            dir_obj.get_file_key('README', obnamlib.REPO_FILE_MODE),
            None)

    def test_sets_file_key(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.set_file_key('README', obnamlib.REPO_FILE_MODE, 0123)
        self.assertEqual(
            dir_obj.get_file_key('README', obnamlib.REPO_FILE_MODE),
            0123)

    def test_raises_error_if_mutable_and_file_key_is_set(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.set_file_key, 'README', obnamlib.REPO_FILE_MODE, 0123)

    def test_file_has_no_chunk_ids_initially(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        self.assertEqual(dir_obj.get_file_chunk_ids('README'), [])

    def test_appends_file_chunk_ids(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.append_file_chunk_id('README', 'chunk-1')
        dir_obj.append_file_chunk_id('README', 'chunk-2')
        self.assertEqual(
            dir_obj.get_file_chunk_ids('README'),
            ['chunk-1', 'chunk-2'])

    def test_clears_file_chunk_ids(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.append_file_chunk_id('README', 'chunk-1')
        dir_obj.append_file_chunk_id('README', 'chunk-2')
        dir_obj.clear_file_chunk_ids('README')
        self.assertEqual(dir_obj.get_file_chunk_ids('README'), [])

    def test_raises_error_if_mutable_and_file_chunk_id_is_appended(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.append_file_chunk_id, 'README', 'chunk-1')

    def test_raises_error_if_mutable_and_file_chunk_ids_are_cleared(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_file('README')
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.clear_file_chunk_ids, 'README')

    def test_has_no_subdirs_initially(self):
        dir_obj = obnamlib.GADirectory()
        self.assertEqual(dir_obj.get_subdir_basenames(), [])

    def test_adds_subdir(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_subdir('.git', 'obj-id')
        self.assertEqual(dir_obj.get_subdir_basenames(), ['.git'])

    def test_raises_error_if_mutable_and_subdir_is_added(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.add_subdir, '.git', 'obj-id')

    def test_removes_subdir(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_subdir('.git', 'obj-id')
        dir_obj.remove_subdir('.git')
        self.assertEqual(dir_obj.get_subdir_basenames(), [])

    def test_removes_nonexistent_subdir(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.remove_subdir('.git')
        self.assertEqual(dir_obj.get_subdir_basenames(), [])

    def test_raises_error_if_mutable_and_subdir_is_removed(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.set_immutable()
        self.assertRaises(
            obnamlib.GAImmutableError,
            dir_obj.remove_subdir, '.git')

    def test_returns_subdir_object_id(self):
        dir_obj = obnamlib.GADirectory()
        dir_obj.add_subdir('.git', 'obj-id')
        self.assertEqual(dir_obj.get_subdir_object_id('.git'), 'obj-id')

    def test_returns_None_for_subdir_object_id_if_subdir_does_not_exist(self):
        dir_obj = obnamlib.GADirectory()
        self.assertEqual(dir_obj.get_subdir_object_id('.git'), None)


class GADirectoryCreationTests(unittest.TestCase):

    def test_creates_GADirectory_from_dict(self):
        orig = obnamlib.GADirectory()
        orig.add_file('.')
        orig.set_file_key(
            '.', obnamlib.REPO_FILE_MODE, stat.S_IFDIR | 0755)
        orig.add_file('README')
        orig.set_file_key(
            'README', obnamlib.REPO_FILE_MODE, stat.S_IFREG | 0644)
        orig.add_subdir('.git', 'git-dir-id')

        new = obnamlib.create_gadirectory_from_dict(orig.as_dict())
        self.assertEqual(new.as_dict(), orig.as_dict())
