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


import os

import obnamlib


class GATree(object):

    '''Manage a tree of directory objects.

    This class manages a tree of directory objects in such a way that
    the caller may refer to directories using full pathnames. It will
    allow referring to any directory, and will create any missing
    parent directory objects as needed. Existing directory objects
    will be updated in a copy-on-write manner. The class maintains a
    reference to the root directory objects, and updates the reference
    if it needs to be changed.

    '''

    def __init__(self):
        self._blob_store = None
        self._root_dir_id = None
        self._cache = DirectoryObjectCache()

    def set_blob_store(self, blob_store):
        self._blob_store = blob_store

    def set_root_directory_id(self, root_dir_id):
        self._root_dir_id = root_dir_id

    def get_root_directory_id(self):
        return self._root_dir_id

    def get_directory(self, pathname):
        dir_obj = self._cache.get(pathname)
        if dir_obj is not None:
            return dir_obj

        if self._root_dir_id is None:
            return None

        dir_obj = None
        if pathname == '/':
            dir_obj = self._get_dir_obj(self._root_dir_id)
        else:
            parent_obj = self._get_containing_dir_obj(pathname)
            if parent_obj is not None:
                basename = os.path.basename(pathname)
                obj_id = parent_obj.get_subdir_object_id(basename)
                if obj_id is not None:
                    dir_obj = self._get_dir_obj(obj_id)

        if dir_obj is not None:
            self._cache.set(pathname, dir_obj)

        return dir_obj

    def _get_dir_obj(self, dir_id):
        blob = self._blob_store.get_blob(dir_id)
        if blob is None:  # pragma: no cover
            return None
        as_dict = obnamlib.deserialise_object(blob)
        dir_obj = obnamlib.create_gadirectory_from_dict(as_dict)
        dir_obj.set_immutable()
        return dir_obj

    def _get_containing_dir_obj(self, pathname):
        parent_path = os.path.dirname(pathname)
        return self.get_directory(parent_path)

    def set_directory(self, pathname, dir_obj):
        self._cache.set(pathname, dir_obj)
        if pathname != '/':
            basename = os.path.basename(pathname)
            parent_path = os.path.dirname(pathname)
            parent_obj = self._cache.get(parent_path)
            if not parent_obj:
                parent_obj = self.get_directory(parent_path)
                if parent_obj:
                    parent_obj = obnamlib.create_gadirectory_from_dict(
                        parent_obj.as_dict())
                else:
                    parent_obj = obnamlib.GADirectory()
                    parent_obj.add_file('.')
            if not parent_obj.is_mutable():
                parent_obj = obnamlib.create_gadirectory_from_dict(
                    parent_obj.as_dict())
            parent_obj.add_subdir(basename, None)
            self.set_directory(parent_path, parent_obj)

    def remove_directory(self, pathname):
        if pathname == '/':
            self._remove_root_dir()
        else:
            self._remove_from_parent(pathname)

    def _remove_root_dir(self):
        self._root_dir_id = None
        self._cache.clear()

    def _remove_from_parent(self, pathname):
        self._cache.remove(pathname)
        basename = os.path.basename(pathname)
        parent_path = os.path.dirname(pathname)
        parent_obj = self._cache.get(parent_path)
        if not parent_obj:
            parent_obj = self.get_directory(parent_path)
            if parent_obj:
                parent_obj = obnamlib.create_gadirectory_from_dict(
                    parent_obj.as_dict())
        if parent_obj:
            parent_obj.remove_subdir(basename)
            self.set_directory(parent_path, parent_obj)

    def flush(self):
        if '/' in self._cache:
            self._root_dir_id = self._fixup_subdir_refs('/')
        self._blob_store.flush()
        self._cache.clear()

    def flush_ro(self):  # pragma: no cover
        self._cache.clear()

    def _fixup_subdir_refs(self, pathname):
        dir_obj = self._cache.get(pathname)
        assert dir_obj is not None, 'expected %s in cache' % pathname
        for basename in dir_obj.get_subdir_basenames():
            if dir_obj.get_subdir_object_id(basename) is None:
                subdir_path = os.path.join(pathname, basename)
                subdir_id = self._fixup_subdir_refs(subdir_path)
                dir_obj.add_subdir(basename, subdir_id)
        return self._put_dir_obj(dir_obj)

    def _put_dir_obj(self, dir_obj):
        dir_obj.set_immutable()
        blob = obnamlib.serialise_object(dir_obj.as_dict())
        return self._blob_store.put_blob(blob)


class DirectoryObjectCache(object):

    def __init__(self):
        self.clear()
        self._max_objs = 10**5

    def _clear_immutable(self):  # pragma: no cover
        if len(self._objs) >= self._max_objs:
            for pathname, dirobj in self._objs.items():
                if not dirobj.is_mutable():
                    del self._objs[pathname]

    def clear(self):
        self._objs = {}

    def set(self, pathname, dir_obj):
        self._objs[pathname] = dir_obj
        self._clear_immutable()

    def get(self, pathname):
        return self._objs.get(pathname)

    def __contains__(self, pathname):
        return pathname in self._objs

    def remove(self, pathname):
        if pathname in self._objs:
            del self._objs[pathname]
