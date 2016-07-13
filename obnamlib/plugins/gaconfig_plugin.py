# Copyright (C) 2015  Lars Wirzenius
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


import obnamlib


class FormatGreenAlbatrossConfigPlugin(obnamlib.ObnamPlugin):

    def enable(self):
        # Add settings related to FORMAT GREEN ALBATROSS.

        ga_group = obnamlib.option_group['green-albatross'] = (
            'Repository format green-albatross')

        self.app.settings.bytesize(
            ['dir-cache-size'],
            'size of in-memory cache for DIR objects',
            metavar='SIZE',
            default=obnamlib.DEFAULT_DIR_CACHE_BYTES,
            group=ga_group)

        self.app.settings.bytesize(
            ['dir-bag-size'],
            'approximate maximum size of bags combining many DIR objects',
            metavar='SIZE',
            default=obnamlib.DEFAULT_DIR_BAG_BYTES,
            group=ga_group)

        self.app.settings.bytesize(
            ['chunk-cache-size'],
            'size of in-memory cache for file data chunk objects',
            metavar='SIZE',
            default=obnamlib.DEFAULT_CHUNK_CACHE_BYTES,
            group=ga_group)

        self.app.settings.bytesize(
            ['chunk-bag-size'],
            'approximate maximum size of bag combining many chunk objects',
            metavar='SIZE',
            default=obnamlib.DEFAULT_CHUNK_BAG_BYTES,
            group=ga_group)
