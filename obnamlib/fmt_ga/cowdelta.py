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


class CowDelta(object):

    def __init__(self):
        self._dict = {}

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._dict.keys()

    def set(self, key, value):
        self._dict[key] = value

    def get(self, key):
        return self._dict[key]

    def remove(self, key):
        self._dict[key] = removed_key


removed_key = object()
