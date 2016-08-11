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


import obnamlib


_short_key_names = {
    obnamlib.REPO_FILE_TEST_KEY: 'T',
    obnamlib.REPO_FILE_USERNAME: 'U',
    obnamlib.REPO_FILE_GROUPNAME: 'G',
    obnamlib.REPO_FILE_SYMLINK_TARGET: 'S',
    obnamlib.REPO_FILE_XATTR_BLOB: 'X',
    obnamlib.REPO_FILE_MD5: '5',
    obnamlib.REPO_FILE_MODE: 'M',
    obnamlib.REPO_FILE_MTIME_SEC: 'ms',
    obnamlib.REPO_FILE_MTIME_NSEC: 'mn',
    obnamlib.REPO_FILE_ATIME_SEC: 'as',
    obnamlib.REPO_FILE_ATIME_NSEC: 'an',
    obnamlib.REPO_FILE_NLINK: 'N',
    obnamlib.REPO_FILE_SIZE: 's',
    obnamlib.REPO_FILE_UID: 'u',
    obnamlib.REPO_FILE_GID: 'g',
    obnamlib.REPO_FILE_BLOCKS: 'B',
    obnamlib.REPO_FILE_DEV: 'D',
    obnamlib.REPO_FILE_INO: 'I',
    obnamlib.REPO_FILE_SHA224: '224',
    obnamlib.REPO_FILE_SHA256: '256',
    obnamlib.REPO_FILE_SHA384: '384',
    obnamlib.REPO_FILE_SHA512: '512',
}

# Let's make sure we have no duplicate values.
assert len(_short_key_names) == len(_short_key_names.values())

_key_from_short = dict((v, k) for k, v in _short_key_names.items())


class GADirectory(object):

    def __init__(self):
        obnamlib.object_created(self)
        self._dict = {
            'metadata': {},
            'subdirs': {},
        }
        self._mutable = True

    def __del__(self):
        obnamlib.object_deleted(self, self._dict)

    def is_mutable(self):
        return self._mutable

    def set_immutable(self):
        self._mutable = False

    def as_dict(self):
        return self._dict

    def set_from_dict(self, a_dict):
        self._dict = a_dict

    def add_file(self, basename):
        if basename not in self._dict['metadata']:
            self._require_mutable()
            self._dict['metadata'][basename] = {
                'chunk-ids': [],
            }

    def _require_mutable(self):
        if not self._mutable:
            raise GAImmutableError()

    def remove_file(self, basename):
        if basename in self._dict['metadata']:
            self._require_mutable()
            if basename in self._dict['metadata']:
                del self._dict['metadata'][basename]

    def get_file_basenames(self):
        return self._dict['metadata'].keys()

    def get_file_key(self, basename, key):
        short_name = self.get_short_key_name(key)
        return self._dict['metadata'][basename].get(short_name)

    def set_file_key(self, basename, key, value):
        short_name = self.get_short_key_name(key)
        old_value = self._dict['metadata'][basename].get(short_name, None)
        if value != old_value:
            self._require_mutable()
            self._dict['metadata'][basename][short_name] = value

    def get_short_key_name(self, key):
        '''Translate a key id to a short key name.

        This is similar to obnamlib.repo_key_name, but the name is
        guaranteed to be short, while still being unique. The length
        matters, as these names will be used a lot.

        '''

        return _short_key_names[key]

    def get_key_from_short_name(self, short_name):
        '''Inverse of get_short_key_name.'''
        return _key_from_short[short_name]

    def get_file_chunk_ids(self, basename):
        return self._dict['metadata'][basename]['chunk-ids']

    def append_file_chunk_id(self, basename, chunk_id):
        self._require_mutable()
        self._dict['metadata'][basename]['chunk-ids'].append(chunk_id)

    def clear_file_chunk_ids(self, basename):
        self._require_mutable()
        self._dict['metadata'][basename]['chunk-ids'] = []

    def get_subdir_basenames(self):
        return self._dict['subdirs'].keys()

    def add_subdir(self, basename, obj_id):
        self._require_mutable()
        self._dict['subdirs'][basename] = obj_id

    def remove_subdir(self, basename):
        self._require_mutable()
        if basename in self._dict['subdirs']:
            del self._dict['subdirs'][basename]

    def get_subdir_object_id(self, basename):
        return self._dict['subdirs'].get(basename)


class GAImmutableError(obnamlib.ObnamError):

    msg = 'Attempt to modify an immutable GADirectory'


def create_gadirectory_from_dict(a_dict):
    dir_obj = GADirectory()
    dir_obj.set_from_dict(a_dict)
    return dir_obj
