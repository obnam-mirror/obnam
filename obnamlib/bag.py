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


class Bag(object):

    def __init__(self):
        obnamlib.object_created(self)
        self._bag_id = None
        self._blobs = []
        self._blobs_bytes = 0

    def __del__(self):
        obnamlib.object_deleted(self, self._blobs)

    def get_id(self):
        return self._bag_id

    def set_id(self, bag_id):
        assert isinstance(bag_id, (int, long, str))
        self._bag_id = bag_id

    def append(self, blob):
        if self.get_id() is None:
            raise BagIdNotSetError()
        self._blobs.append(blob)
        self._blobs_bytes += len(blob)
        return obnamlib.make_object_id(self.get_id(), len(self) - 1)

    def __len__(self):
        return len(self._blobs)

    def get_bytes(self):
        return self._blobs_bytes

    def __getitem__(self, index):
        return self._blobs[index]


class BagIdNotSetError(obnamlib.ObnamError):

    msg = 'Bag id not set: cannot append a blob (programming error)'


def make_object_id(bag_id, object_index):
    if isinstance(bag_id, str):
        assert object_index == 0
        return '%s.%d' % (bag_id, object_index)
    return '%016x.%d' % (bag_id, object_index)


def parse_object_id(object_id):
    parts = object_id.split('.', 1)
    return int(parts[0], 16), int(parts[1])
