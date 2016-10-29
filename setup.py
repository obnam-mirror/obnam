#!/usr/bin/env python
# Copyright (C) 2008-2016  Lars Wirzenius <liw@liw.fi>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from distutils.core import setup, Extension
from distutils.cmd import Command
from distutils.command.build import build
from distutils.command.clean import clean
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

import cliapp

import obnamlib


# We need to know whether we can run yarn. We do this by checking
# the python-markdown version: if it's new enough, we assume yarn
# is available, and if it isn't, yarn won't be available since it
# won't work with old versions (e.g., the one in Debian squeeze.)

try:
    import markdown
except ImportError:
    got_yarn = False
else:
    if (hasattr(markdown, 'extensions') and
        hasattr(markdown.extensions, 'Extension')):
        got_yarn = True
    else:
        got_yarn = False


def runcmd(*args, **kwargs):
    try:
        subprocess.check_call(*args, **kwargs)
    except subprocess.CalledProcessError, e:
        sys.stderr.write('ERROR: %s\n' % str(e))
        sys.exit(1)


class Build(build):

    def run(self):
        build.run(self)
        self.build_manpage('obnam', '')
        self.build_manpage('obnam', '.de')

    def build_manpage(self, program, lang):
        print 'building manpage for %s (lang=%s)' % (program, lang)
        self.generate_troff(program, lang)

    def generate_troff(self, program, lang):
        with open('%s.1%s' % (program, lang), 'w') as f:
            cliapp.runcmd(
                ['python', program,
                 '--generate-manpage=%s.1%s.in' % (program, lang),
                 '--output=%s.1' % program],
                stdout=f)


class BuildDocs(Command):

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        print 'building manual'
        runcmd(['make', '-C', 'manual'])

        print 'building yarns'
        runcmd(['make', '-C', 'yarns'])

        self.format_txt('obnam')

    def format_txt(self, program):
        env = dict(os.environ)
        env['MANWIDTH'] = '80'
        with open('%s.1.txt' % program, 'w') as f:
            cliapp.runcmd(
                ['man', '-l', '%s.1' % program],
                ['col', '-b'],
                stdout=f,
                env=env)

class CleanMore(clean):

    def run(self):
        clean.run(self)
        for x in ['obnam.1', 'obnam-benchmark.1', '.coverage',
                  'obnamlib/_obnam.so']:
            if os.path.exists(x):
                os.remove(x)
        self.remove_pyc('obnamlib')
        self.remove_pyc('test-plugins')
        if os.path.isdir('build'):
            if os.path.islink('build'):
                for path in os.listdir('build'):
                    shutil.rmtree('build/' + path)
            else:
                shutil.rmtree('build')

    def remove_pyc(self, rootdir):
        for dirname, subdirs, basenames in os.walk(rootdir):
            for x in [os.path.join(dirname, base)
                       for base in basenames
                       if base.endswith('.pyc')]:
                os.remove(x)

class Check(Command):

    user_options = [
        ('unit-tests', 'u', 'run unit tests?'),
        ('yarns', 'y', 'run yarn tests locally?'),
        ('all-yarns', 'Y', 'run ALL yarn tests (require ASSUMING)?'),
        ('lock-tests', 'l', 'run lock tests locally?'),
        ('network-lock-tests', 'L', 'run lock tests against localhost?'),
        ('crash-tests', 'c', 'run crash tests?'),
        ('sftp-tests', 's', 'run sftp tests against localhost?'),
        ('nitpick', 'n', 'check copyright statements, line lengths, etc'),
    ]

    def set_all_options(self, new_value):
        self.unit_tests = new_value
        self.yarns = new_value
        self.all_yarns = new_value
        self.lock_tests = new_value
        self.network_lock_tests = new_value
        self.crash_tests = new_value
        self.sftp_tests = new_value
        self.nitpick = new_value

    def initialize_options(self):
        self.set_all_options(False)

    def finalize_options(self):
        any_set = (
            self.unit_tests or
            self.yarns or
            self.all_yarns or
            self.lock_tests or
            self.network_lock_tests or
            self.crash_tests or
            self.sftp_tests or
            self.nitpick)
        if not any_set:
            self.set_all_options(True)

    def run(self):
        if self.unit_tests:
            self.run_unit_tests()

        if self.nitpick:
            self.run_nitpick_checks()

        if (self.yarns or self.all_yarns) and got_yarn:
            self.run_yarn()

        num_clients = '2'
        num_generations = '16'

        if self.sftp_tests:
            self.run_sftp_test()

        if self.lock_tests:
            self.run_lock_test(num_clients, num_generations)

        if self.network_lock_tests:
            self.run_network_lock_test(num_clients, num_generations)

        if self.crash_tests:
            self.run_crash_test()

        print "setup.py check done"

    def run_unit_tests(self):
        print "run unit tests"
        runcmd(['python', '-m', 'CoverageTestRunner',
                '--ignore-missing-from=without-tests'])
        if os.path.exists('.coverage'):
            os.remove('.coverage')

    def run_yarn(self):
        for repo_format in self.get_wanted_formats():
            self.run_yarn_for_repo_format(repo_format)

    def get_wanted_formats(self):
        if 'REPOSITORY_FORMAT' in os.environ:
            return [os.environ['REPOSITORY_FORMAT']]
        else:
            return cliapp.runcmd(['./obnam', '--no-default-configs',
                                  'list-formats']).splitlines()

    def run_yarn_for_repo_format(self, repo_format):
        print 'run yarn for repository format %s' % repo_format
        argv = ['yarn', '-s', 'yarns/obnam.sh',
                '--env', 'REPOSITORY_FORMAT=' + repo_format]
        if self.all_yarns:
            argv.append('--require-assumptions')
        runcmd(argv + glob.glob('yarns/*.yarn'))

    def run_lock_test(self, num_clients, num_generations):
        print "run local locking tests"
        test_repo = tempfile.mkdtemp()
        runcmd(['./test-locking', num_clients,
                num_generations, test_repo, test_repo])
        shutil.rmtree(test_repo)

    def run_network_lock_test(self, num_clients, num_generations):
        print "run locking tests using localhost networking"
        test_repo = tempfile.mkdtemp()
        repo_url = 'sftp://localhost/%s' % test_repo
        runcmd(['./test-locking', num_clients,
                num_generations, repo_url, test_repo])
        shutil.rmtree(test_repo)

    def run_crash_test(self):
        print "run crash test"
        runcmd(['./crash-test', '200'])

    def run_sftp_test(self):
        print "run sftp tests"
        runcmd(['./test-sftpfs'])

    def run_nitpick_checks(self):
        self.check_with_pep8()
        self.check_with_pylint()
        if os.path.exists('.git'):
            sources = self.find_all_source_files()
            self.check_sources_for_nitpicks(sources)
            self.check_copyright_statements(sources)
        else:
            print "no .git, no nitpick for you"

    def check_with_pep8(self):
        output = cliapp.runcmd(['pep8', '--version'])
        parts = output.strip().split('.')
        # pep8 version 1.5.7 is in Debian jessie. Previous versions
        # give bad warnings about whitespace around some operators,
        # and later versions don't. So we only run pep8 if it's new
        # enough.
        if parts >= ['1', '5', '7']:
            print 'running pep8'
            cliapp.runcmd(['pep8', 'obnamlib'], stdout=None, stderr=None)
        else:
            print 'not running pep8'

    def check_with_pylint(self):
        output = cliapp.runcmd(['pylint', '--version'])
        parts = output.splitlines()[0].split('.')
        # pylint version 1.3.1 is in Debian jessie. Previous versions
        # do not know all the things in the pylint.conf file we use,
        # so we only run pylint if it's new enough.
        if parts >= ['pylint 1', '3', '1,']:
            print 'running pylint'
            cliapp.runcmd(
                ['pylint', '--rcfile=pylint.conf', 'obnamlib'],
                stdout=None, stderr=None)
        else:
            print 'not running pylint', parts

    def check_sources_for_nitpicks(self, sources):
        cliapp.runcmd(['./nitpicker'] + sources, stdout=None, stderr=None)

    def check_copyright_statements(self, sources):
        if self.copylint_is_available():
            print 'check copyright statements in source files'
            cliapp.runcmd(['copyright-statement-lint'] + sources)
        else:
            print 'no copyright-statement-lint: no copyright checks'

    def copylint_is_available(self):
        returncode, stdout, stderr = cliapp.runcmd_unchecked(
            ['sh', '-c', 'command -v copyright-statement-lint'])
        return returncode == 0

    def find_all_source_files(self):
        exclude = [
            r'\.gpg$',
            r'/random_seed$',
            r'\.gz$',
            r'\.xz$',
            r'\.yarn$',
            r'\.mdwn$',
            r'\.css$',
            r'\.conf$',
            r'^without-tests$',
            r'^test-plugins/.*\.py$',
            r'^debian/',
            r'^README\.',
            r'^NEWS$',
            r'^COPYING$',
            r'^CC-BY-SA-4\.0\.txt$',
            r'^\.gitignore$',
            r'^obnamlib/version\.py$',
            ]

        pats = [re.compile(x) for x in exclude]

        output = cliapp.runcmd(['git', 'ls-files'])
        result = []
        for line in output.splitlines():
            for pat in pats:
                if pat.search(line):
                    break
            else:
                result.append(line)
        return result


setup(name='obnam',
      version=obnamlib.__version__,
      description='Backup software',
      author='Lars Wirzenius',
      author_email='liw@liw.fi',
      url='http://obnam.org/',
      scripts=['obnam', 'obnam-viewprof'],
      packages=[
          'obnamlib',
          'obnamlib.plugins',
          'obnamlib.fmt_6',
          'obnamlib.fmt_ga',
      ],
      ext_modules=[Extension('obnamlib._obnam', sources=['_obnammodule.c'])],
      data_files=[('share/man/man1', glob.glob('*.1'))],
      cmdclass={
        'build': Build,
        'docs': BuildDocs,
        'check': Check,
        'clean': CleanMore,
      },
     )
