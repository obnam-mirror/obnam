# Copyright 2015-2017  Lars Wirzenius
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


import errno
import logging
import os
import random

import tracing

import obnamlib


# Start with a new random id after this many sequential ones.
# This avoids putting all the ids in one directory.
MAX_IDS_UNTIL_RESET = 512


class BagStore(object):

    def __init__(self):
        self._fs = None
        self._dirname = None
        self._id_inventor = IdInventor()
        self._id_inventor.set_filename_maker(self._make_bag_filename)

    def _make_bag_filename(self, bag_id):
        if isinstance(bag_id, str):
            return os.path.join(self._dirname, '%s.bag' % bag_id)

        basename = '%016x' % bag_id
        return os.path.join(
            self._dirname,
            basename[0:2],
            basename[2:4],
            basename[4:6],
            '%s.bag' % basename)

    def set_location(self, fs, dirname):
        self._fs = fs
        self._dirname = dirname
        self._id_inventor.set_fs(fs)

    def reserve_bag_id(self):
        reserved = self._id_inventor.reserve_id()
        tracing.trace('id=%r', reserved)
        return reserved

    def put_bag(self, bag):
        filename = self._make_bag_filename(bag.get_id())
        serialised = serialise_bag(bag)
        self._fs.overwrite_file(filename, serialised)

    def get_bag(self, bag_id):
        filename = self._make_bag_filename(bag_id)
        serialised = self._fs.cat(filename)
        return deserialise_bag(serialised)

    def has_bag(self, bag_id):
        filename = self._make_bag_filename(bag_id)
        try:
            st = self._fs.lstat(filename)
        except (IOError, OSError):  # pragma: no cover
            return False
        return st.st_size > 0

    def get_bag_ids(self):
        for pathname, _ in self._fs.scan_tree(self._dirname):
            if self._is_bag_filename(pathname):
                yield self._get_bag_id_from_filename(pathname)

    def _is_bag_filename(self, pathname):
        return pathname.endswith('.bag')

    def _get_bag_id_from_filename(self, pathname):
        basename = os.path.basename(pathname)
        return int(basename[:-len('.bag')], 16)

    def remove_bag(self, bag_id):
        filename = self._make_bag_filename(bag_id)
        try:
            self._fs.remove(filename)
        except EnvironmentError as e:  # pragma: no cover
            logging.warning(
                'Tried to delete %s which does not exist:%d:%s',
                filename, e.errno, str(e))


class IdInventor(object):

    def __init__(self):
        self.set_fs(None)
        self._filename_maker = None

    def set_fs(self, fs):
        self._fs = fs
        self._reset_ids()

    def _reset_ids(self):
        self._prev_id = None
        self._ids_since_reset = 0
        self._max_ids_until_reset = MAX_IDS_UNTIL_RESET

    def set_filename_maker(self, maker):
        self._filename_maker = maker

    def reserve_id(self):
        while True:
            if self._time_to_reset_ids():  # pragma: no cover
                self._reset_ids()
            self._next_id()
            if self._reserve_succeeds():
                return self._prev_id
            self._prev_id = None  # pragma: no cover

    def _time_to_reset_ids(self):
        return self._ids_since_reset >= self._max_ids_until_reset

    def _next_id(self):
        if self._prev_id is None:
            self._prev_id = random.randint(0, obnamlib.MAX_ID)
        else:
            self._prev_id += 1  # pragma: no cover
        self._ids_since_reset += 1

    def _reserve_succeeds(self):
        filename = self._filename_maker(self._prev_id)
        try:
            self._fs.write_file(filename, '')
        except OSError as e:  # pragma: no cover
            if e.errno == errno.EEXIST:
                return False
            raise
        return True


def serialise_bag(bag):
    obj = {
        'bag-id': bag.get_id(),
        'blobs': [bag[i] for i in range(len(bag))],
    }
    return obnamlib.serialise_object(obj)


def deserialise_bag(serialised):
    obj = obnamlib.deserialise_object(serialised)
    bag = obnamlib.Bag()
    bag.set_id(obj['bag-id'])
    for blob in obj['blobs']:
        bag.append(blob)
    return bag
