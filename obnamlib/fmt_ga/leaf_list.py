# Copyright 2016-2017  Lars Wirzenius
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


class LeafList(object):

    def __init__(self):
        self._leaves = []

    def serialise(self):
        return self._leaves

    @classmethod
    def unserialise(cls, serialised):
        ll = LeafList()
        for leaf_info in serialised:
            ll.add(
                leaf_info['leaf_id'],
                leaf_info['first_key'],
                leaf_info['last_key']
            )
        return ll

    def __len__(self):
        return len(self._leaves)

    def leaves(self):
        return [leaf_info['leaf_id'] for leaf_info in self._leaves]

    def add(self, leaf_id, first_key, last_key):
        if any(self.find_leaf(k) for k in [first_key, last_key]):
            raise Exception(
                'Overlapping key range {}..{}'.format(first_key, last_key))

        self._leaves.append({
            'first_key': first_key,
            'last_key': last_key,
            'leaf_id': leaf_id,
        })
        self._leaves.sort(key=lambda x: (x['first_key'], x['last_key']))

    def find_leaf(self, key):
        for leaf_info in self._leaves:
            if leaf_info['first_key'] <= key <= leaf_info['last_key']:
                return leaf_info['leaf_id']
        return None
