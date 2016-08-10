# Copyright (C) 2016  Lars Wirzenius
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


import logging

import obnamlib


def object_created(obj):
    logging.debug('object_created: %s %s', obj.__class__.__name__, id(obj))


def object_deleted(obj, serialisable_obj):
    logging.debug(
        'object_deleted: %s %s',
        id(obj),
        len(obnamlib.serialise_object(serialisable_obj)))
