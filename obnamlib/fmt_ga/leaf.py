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


import copy


class CowLeaf(object):

    def __init__(self):
        self._dict = {}

    def __len__(self):
        return len(self._dict)

    def keys(self):
        return self._dict.keys()

    def lookup(self, key):
        return self._dict.get(key, None)

    def insert(self, key, value):
        self._dict[key] = value

    def remove(self, key):
        if key in self._dict:
            del self._dict[key]

    def as_dict(self):
        return copy.deepcopy(self._dict)

    def from_dict(self, a_dict):
        self._dict = a_dict
