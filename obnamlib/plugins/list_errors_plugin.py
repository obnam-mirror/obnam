# Copyright (C) 2015-2016  Lars Wirzenius
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


import textwrap

import obnamlib


class ListErrorsPlugin(obnamlib.ObnamPlugin):

    def enable(self):
        self.app.add_subcommand(
            'list-errors', self.list_errors, arg_synopsis='')

    def list_errors(self, args):
        errors = obnamlib.find_structured_errors(obnamlib, self.app.pluginmgr)
        errors  = [e for e in errors if e.msg]
        f = self.app.output

        f.write('## By error code\n\n')
        for error in sorted(errors, key=lambda e: e().id):
            f.write('* `{} {}`\n'.format(error().id, error.__name__))
        f.write('\n\n')

        f.write('## By name\n\n')
        for error in sorted(errors, key=lambda e: e.__name__):
            f.write('`{}` (`{}`)\n'.format(error.__name__, error().id))
            f.write(':   {}\n'.format(self.indent(error.msg).lstrip()))
            f.write('\n')

    def indent(self, s):
        s = ''.join(s.rstrip() + '\n' for s in s.splitlines())
        paras = [
            '\n'.join(para.split())
            for para in s.split('\n\n')
            if para.strip()
        ]
        return '\n\n'.join(
            textwrap.fill(para, initial_indent=' '*4, subsequent_indent=' '*4)
            for para in paras)
