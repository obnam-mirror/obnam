# Copyright (C) 2009-2016  Lars Wirzenius
# Copyright (C) 2017  SanskritFritz
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


import re
import stat
import sys
import time

import obnamlib


class ClientDoesNotExistError(obnamlib.ObnamError):

    msg = 'Client {client} does not exist in repository {repo}'


class WrongNumberOfGenerationsForDiffError(obnamlib.ObnamError):

    msg = 'Need one or two generations'


class ShowFirstGenerationError(obnamlib.ObnamError):

    msg = "Can't show first generation. Use 'obnam ls' instead"


class ShowPlugin(obnamlib.ObnamPlugin):

    '''Show information about data in the backup repository.

    This implements commands for listing contents of root and client
    objects, or the contents of a backup generation.

    '''

    leftists = (2, 3, 6)
    min_widths = (1, 1, 1, 1, 6, 20, 1)

    def enable(self):
        self.app.add_subcommand('clients', self.clients)
        self.app.add_subcommand('generations', self.generations)
        self.app.add_subcommand('genids', self.genids)
        self.app.add_subcommand('ls', self.ls, arg_synopsis='[FILE]...')
        self.app.add_subcommand(
            'kdirstat', self.kdirstat, arg_synopsis='[FILE]...')
        self.app.add_subcommand('diff', self.diff,
                                arg_synopsis='[GENERATION1] GENERATION2')
        self.app.add_subcommand('nagios-last-backup-age',
                                self.nagios_last_backup_age)

        self.app.settings.string(
            ['warn-age'],
            'for nagios-last-backup-age: maximum age (by '
            'default in hours) for the most recent '
            'backup before status is warning. '
            'Accepts one char unit specifier '
            '(s,m,h,d for seconds, minutes, hours, '
            'and days.',
            metavar='AGE',
            default=obnamlib.DEFAULT_NAGIOS_WARN_AGE)
        self.app.settings.string(
            ['critical-age'],
            'for nagios-last-backup-age: maximum age '
            '(by default in hours) for the most '
            'recent backup before statis is critical. '
            'Accepts one char unit specifier '
            '(s,m,h,d for seconds, minutes, hours, '
            'and days.',
            metavar='AGE',
            default=obnamlib.DEFAULT_NAGIOS_WARN_AGE)

    def open_repository(self, require_client=True):
        self.app.settings.require('repository')
        if require_client:
            self.app.settings.require('client-name')
        self.repo = self.app.get_repository_object()
        if require_client:
            client = self.app.settings['client-name']
            clients = self.repo.get_client_names()
            if client not in clients:
                raise ClientDoesNotExistError(
                    client=client, repo=self.app.settings['repository'])

    def clients(self, args):
        '''List clients using the repository.'''
        self.open_repository(require_client=False)
        for client_name in self.repo.get_client_names():
            self.app.output.write('%s\n' % client_name)
        self.repo.close()

    def generations(self, args):
        '''List backup generations for client.'''
        self.open_repository()
        client_name = self.app.settings['client-name']
        for gen_id in self.repo.get_client_generation_ids(client_name):
            start = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_STARTED)
            end = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_ENDED)
            is_checkpoint = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_IS_CHECKPOINT)
            file_count = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_FILE_COUNT)
            data_size = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_TOTAL_DATA)

            if is_checkpoint:
                checkpoint = ' (checkpoint)'
            else:
                checkpoint = ''
            sys.stdout.write('%s\t%s .. %s (%d files, %d bytes) %s\n' %
                             (self.repo.make_generation_spec(gen_id),
                              self.format_time(start),
                              self.format_time(end),
                              file_count,
                              data_size,
                              checkpoint))
        self.repo.close()

    def nagios_last_backup_age(self, args):
        '''Check if the most recent generation is recent enough.'''
        try:
            self.open_repository()
        except obnamlib.ObnamError as e:
            self.app.output.write('CRITICAL: %s\n' % e)
            sys.exit(2)

        most_recent = None

        warn_age = self._convert_time(self.app.settings['warn-age'])
        critical_age = self._convert_time(self.app.settings['critical-age'])

        client_name = self.app.settings['client-name']
        for gen_id in self.repo.get_client_generation_ids(client_name):
            start = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_STARTED)
            if most_recent is None or start > most_recent:
                most_recent = start
        self.repo.close()

        now = self.app.time()
        if most_recent is None:
            # the repository is empty / the client does not exist
            self.app.output.write('CRITICAL: no backup found.\n')
            sys.exit(2)
        elif now - most_recent > critical_age:
            self.app.output.write(
                'CRITICAL: backup is old.  last backup was %s.\n' %
                (self.format_time(most_recent)))
            sys.exit(2)
        elif now - most_recent > warn_age:
            self.app.output.write(
                'WARNING: backup is old.  last backup was %s.\n' %
                self.format_time(most_recent))
            sys.exit(1)
        self.app.output.write(
            'OK: backup is recent.  last backup was %s.\n' %
            self.format_time(most_recent))

    def genids(self, args):
        '''List generation ids for client.'''
        self.open_repository()
        client_name = self.app.settings['client-name']
        for gen_id in self.repo.get_client_generation_ids(client_name):
            sys.stdout.write('%s\n' % self.repo.make_generation_spec(gen_id))
        self.repo.close()

    def traverse(self, hdr, cb, args):
        '''Traverse a generation calling callback.'''

        self.open_repository()

        if len(args) is 0:
            args = ['/']

        client_name = self.app.settings['client-name']
        for genspec in self.app.settings['generation']:
            gen_id = self.repo.interpret_generation_spec(client_name, genspec)
            started = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_STARTED)
            ended = self.repo.get_generation_key(
                gen_id, obnamlib.REPO_GENERATION_ENDED)
            started = self.format_time(started)
            ended = self.format_time(ended)
            hdr('Generation %s (%s - %s)\n' %
                (self.repo.make_generation_spec(gen_id), started, ended))
            for filename in args:
                filename = self.remove_trailing_slashes(filename)
                self.show_objects(cb, gen_id, filename)

        self.repo.close()

    def remove_trailing_slashes(self, filename):
        while filename.endswith('/') and filename != '/':
            filename = filename[:-1]
        return filename

    def format_time(self, timestamp):
        prefix = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        return prefix + ' ' + self.format_timezone()

    def format_timezone(self):
        '''Return a timezone indication on +0300 format.'''

        # A zero offset gets a plus sign. The time.timezone value has the
        # opposite sign of what we want in the output.
        if time.timezone <= 0:
            sign = '+'
        else:
            sign = '-'

        hh = abs(time.timezone) / 3600
        mm = (abs(time.timezone) % 3600) / 60
        return '%c%02d%02d' % (sign, hh, mm)

    def isdir(self, gen_id, filename):
        mode = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_MODE)
        return stat.S_ISDIR(mode)

    def show_objects(self, cb, gen_id, dirname):
        cb(gen_id, dirname)
        subdirs = []
        for filename in sorted(self.repo.get_file_children(gen_id, dirname)):
            if self.isdir(gen_id, filename):
                subdirs.append(filename)
            else:
                cb(gen_id, filename)

        for subdir in subdirs:
            self.show_objects(cb, gen_id, subdir)

    def ls(self, args):
        '''List contents of a generation.'''
        self.traverse(self.show_hdr_ls, self.show_item_ls, args)

    def show_hdr_ls(self, comment):
        self.app.output.write(comment)

    def show_item_ls(self, gen_id, filename):
        fields = self.fields(gen_id, filename)
        widths = [
            1,   # mode
            5,   # nlink
            -8,  # owner
            -8,  # group
            10,  # size
            1,   # mtime
            -1,  # name
        ]

        result = []
        for i, field in enumerate(fields):
            if widths[i] < 0:
                fmt = '%-*s'
            else:
                fmt = '%*s'
            result.append(fmt % (abs(widths[i]), field))
        self.app.output.write('%s\n' % ' '.join(result))

    def kdirstat(self, args):
        '''List contents of a generation in kdirstat cache format.'''
        self.traverse(self.show_hdr_kdirstat, self.show_item_kdirstat, args)

    def show_hdr_kdirstat(self, comment):
        self.app.output.write('''[kdirstat 4.0 cache file]
# Generated by obnam %s
# Do not edit!
#
# Type  path            size    mtime           <optional fields>

''' % comment)

    def show_item_kdirstat(self, gen_id, filename):
        mode = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_MODE)
        size = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_SIZE)
        mtime_sec = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_MTIME_SEC)

        if stat.S_ISREG(mode):
            mode_str = "F\t"
        elif stat.S_ISDIR(mode):
            mode_str = "D "
        elif stat.S_ISLNK(mode):
            mode_str = "L\t"
        elif stat.S_ISBLK(mode):
            mode_str = "BlockDev\t"
        elif stat.S_ISCHR(mode):
            mode_str = "CharDev\t"
        elif stat.S_ISFIFO(mode):
            mode_str = "FIFO\t"
        elif stat.S_ISSOCK(mode):
            mode_str = "Socket\t"
        else:
            # Unhandled, make it look like a comment
            mode_str = "#UNHANDLED\t"

        enc_filename = filename.replace("%", "%25")
        enc_filename = enc_filename.replace(" ", "%20")
        enc_filename = enc_filename.replace("\t", "%09")

        self.app.output.write(
            "%s%s\t%d\t%#x\n" %
            (mode_str, enc_filename, size, mtime_sec))

    def show_diff_for_file(self, gen_id, fullname, change_char):
        '''Show what has changed for a single file.

        change_char is a single char (+,- or *) indicating whether a file
        got added, removed or altered.

        If --verbose, just show all the details as ls shows, otherwise
        show just the file's full name.

        '''

        if self.app.settings['verbose']:
            sys.stdout.write('%s ' % change_char)
            self.show_item_ls(gen_id, fullname)
        else:
            self.app.output.write('%s %s\n' % (change_char, fullname))

    def show_diff_for_common_file(self, gen_id1, gen_id2, fullname, subdirs):
        changed = False
        if self.isdir(gen_id1, fullname) != self.isdir(gen_id2, fullname):
            changed = True
        elif self.isdir(gen_id2, fullname):
            subdirs.append(fullname)
        else:
            # Files are both present and neither is a directory.
            # Compare md5
            def get_md5(gen_id):
                if obnamlib.REPO_FILE_MD5 in self.repo.get_allowed_file_keys():
                    return self.repo.get_file_key(
                        gen_id, fullname, obnamlib.REPO_FILE_MD5)
            md5_1 = get_md5(gen_id1)
            md5_2 = get_md5(gen_id2)
            if md5_1 != md5_2:
                changed = True
        if changed:
            self.show_diff_for_file(gen_id2, fullname, '*')

    def show_diff(self, gen_id1, gen_id2, dirname):
        # This set contains the files from the old/src generation
        set1 = self.repo.get_file_children(gen_id1, dirname)
        subdirs = []
        # These are the new/dst generation files
        for filename in sorted(self.repo.get_file_children(gen_id2, dirname)):
            if filename in set1:
                # Its in both generations
                set1.remove(filename)
                self.show_diff_for_common_file(
                    gen_id1, gen_id2, filename, subdirs)
            else:
                # Its only in set2 - the file/dir got added
                self.show_diff_for_file(gen_id2, filename, '+')
        for filename in sorted(set1):
            # This was only in gen1 - it got removed
            self.show_diff_for_file(gen_id1, filename, '-')

        for subdir in subdirs:
            self.show_diff(gen_id1, gen_id2, subdir)

    def diff(self, args):
        '''Show difference between two generations.'''

        if len(args) not in (1, 2):
            raise WrongNumberOfGenerationsForDiffError()

        self.open_repository()
        client_name = self.app.settings['client-name']
        if len(args) == 1:
            gen_id2 = self.repo.interpret_generation_spec(
                client_name, args[0])
            # Now we have the dst/second generation for show_diff. Use
            # genids/list_generations to find the previous generation
            genids = self.repo.get_client_generation_ids(client_name)
            index = genids.index(gen_id2)
            if index == 0:
                raise ShowFirstGenerationError()
            gen_id1 = genids[index - 1]
        else:
            gen_id1 = self.repo.interpret_generation_spec(
                client_name, args[0])
            gen_id2 = self.repo.interpret_generation_spec(
                client_name, args[1])

        self.show_diff(gen_id1, gen_id2, '/')
        self.repo.close()

    def fields(self, gen_id, filename):
        mode = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_MODE)
        mtime_sec = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_MTIME_SEC)
        target = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_SYMLINK_TARGET)
        nlink = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_NLINK)
        username = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_USERNAME)
        groupname = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_GROUPNAME)
        size = self.repo.get_file_key(
            gen_id, filename, obnamlib.REPO_FILE_SIZE)

        perms = ['?'] + ['-'] * 9
        tab = [
            (stat.S_IFDIR, 0, 'd'),
            (stat.S_IFCHR, 0, 'c'),  # character device
            (stat.S_IFBLK, 0, 'b'),  # block device
            (stat.S_IFREG, 0, '-'),
            (stat.S_IFIFO, 0, 'p'),
            (stat.S_IFLNK, 0, 'l'),
            # (stat.S_IFSOCK, 0, 's'),  # not stored, listed for completeness
            (stat.S_IRUSR, 1, 'r'),
            (stat.S_IWUSR, 2, 'w'),
            (stat.S_IXUSR, 3, 'x'),
            (stat.S_IRGRP, 4, 'r'),
            (stat.S_IWGRP, 5, 'w'),
            (stat.S_IXGRP, 6, 'x'),
            (stat.S_IROTH, 7, 'r'),
            (stat.S_IWOTH, 8, 'w'),
            (stat.S_IXOTH, 9, 'x'),
        ]
        for bitmap, offset, char in tab:
            if (mode & bitmap) == bitmap:
                perms[offset] = char

        # set modifiers based on the x bit in that position
        tab = [
            (stat.S_ISUID, 3, 's', 'S'),
            (stat.S_ISGID, 6, 's', 'S'),
            (stat.S_ISVTX, 9, 't', 'T'),
        ]
        for bitmap, offset, has_X, no_X in tab:
            if mode & bitmap:
                if perms[offset] == 'x':
                    perms[offset] = has_X
                else:
                    perms[offset] = no_X
        perms = ''.join(perms)

        timestamp = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.gmtime(mtime_sec))

        if stat.S_ISLNK(mode):
            name = '%s -> %s' % (filename, target)
        else:
            name = filename

        return (perms,
                str(nlink),
                username,
                groupname,
                str(size),
                timestamp,
                name)

    def align(self, width, field, field_no):
        if field_no in self.leftists:
            return '%-*s' % (width, field)
        else:
            return '%*s' % (width, field)

    def _convert_time(self, s, default_unit='h'):
        m = re.match('([0-9]+)([smhdw])?$', s)
        if m is None:
            raise ValueError
        ticks = int(m.group(1))
        unit = m.group(2)
        if unit is None:
            unit = default_unit

        if unit == 's':
            pass
        elif unit == 'm':
            ticks *= 60
        elif unit == 'h':
            ticks *= 60*60
        elif unit == 'd':
            ticks *= 60*60*24
        elif unit == 'w':
            ticks *= 60*60*24*7
        else:
            raise ValueError
        return ticks
