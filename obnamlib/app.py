# Copyright (C) 2009, 2011  Lars Wirzenius
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
import os
import socket
import tracing

import obnamlib


class App(object):

    '''Main program for backup program.'''
    
    def __init__(self):

        self.setup_config()        

        self.pm = obnamlib.PluginManager()
        self.pm.locations = [self.plugins_dir()]
        self.pm.plugin_arguments = (self,)
        
        self.interp = obnamlib.Interpreter()
        self.register_command = self.interp.register

        self.setup_hooks()

        self.fsf = obnamlib.VfsFactory()
        
    def setup_config(self):
        self.config = obnamlib.Configuration([])
        self.config.new_string(['log'], 'name of log file (%default)')
        self.config['log'] = 'obnam.log'
        self.config.new_string(['log-level'], 
                               'log level, one of debug, info, warning, '
                               'error, critical (%default)')
        self.config['log-level'] = 'info'
        self.config.new_string(['log-keep'],
                               'how many log files to keep? For normal users '
                               'only (default: %default)')
        self.config['log-keep'] = '10'
        self.config.new_bytesize(['log-max'],
                                 'how large can a log file get before getitng '
                                 'rotated (%default)')
        self.config['log-max'] = '1m'
        self.config.new_string(['repository'], 'name of backup repository')
        self.config.new_string(['client-name'], 'name of client (%default)')
        self.config['client-name'] = self.deduce_client_name()
        self.config.new_boolean(['pretend', 'dry-run', 'no-act'],
                                'do not write or remove anything, just '
                                'pretend to do that')

        self.config.new_bytesize(['node-size'],
                                 'size of B-tree nodes on disk '
                                 '(default: %default)')
        self.config['node-size'] = '%s' % obnamlib.DEFAULT_NODE_SIZE

        self.config.new_bytesize(['chunk-size'],
                                 'size of chunks of file data backed up '
                                 '(default: %default)')
        self.config['chunk-size'] = '%s' % obnamlib.DEFAULT_CHUNK_SIZE

        self.config.new_bytesize(['upload-queue-size'],
                                 'length of upload queue for B-tree nodes '
                                 '(default: %default)')
        self.config['upload-queue-size'] = \
            '%s' % obnamlib.DEFAULT_UPLOAD_QUEUE_SIZE

        self.config.new_bytesize(['lru-size'],
                                 'size of LRU cache for B-tree nodes '
                                 '(default: %default)')
        self.config['lru-size'] = '%s' % obnamlib.DEFAULT_LRU_SIZE

        self.config.new_string(['dump-memory-profile'],
                                'make memory profiling dumps '
                                'after each checkpoint and at end? '
                                'set to none, simple, meliae, or heapy '
                                '(default: %default)')
        self.config['dump-memory-profile'] = 'simple'

        self.config.new_list(['trace'],
                                'add to filename patters for which trace '
                                'debugging logging happens')
        
    def deduce_client_name(self):
        return socket.gethostname()

    def setup_hooks(self):
        self.hooks = obnamlib.HookManager()
        self.hooks.new('plugins-loaded')
        self.hooks.new('config-loaded')
        self.hooks.new('shutdown')

        # The Repository class defines some hooks, but the class
        # won't be instantiated until much after plugins are enabled,
        # and since all hooks must be defined when plugins are enabled,
        # we create one instance here, which will immediately be destroyed.
        # FIXME: This is fugly.
        obnamlib.Repository(None, 1000, 1000, 100, self.hooks)

    def plugins_dir(self):
        return os.path.join(os.path.dirname(obnamlib.__file__), 'plugins')

    def rotate_logs(self, filename, keep):
        def rename(old_suffix, counter):
            new_suffix = '.%d' % counter
            if os.path.exists(filename + new_suffix):
                if counter < keep:
                    rename(new_suffix, counter + 1)
                else:
                    os.remove(filename + new_suffix)
            os.rename(filename + old_suffix, filename + new_suffix)
        rename('', 0)

    def setup_logging(self):
        log_filename = self.config['log']
        log_max = self.config['log-max']
        log_keep = int(self.config['log-keep'])
        if (os.path.exists(log_filename) and 
            os.path.getsize(log_filename) > log_max):
            self.rotate_logs(log_filename, log_keep)
        
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler = logging.FileHandler(self.config['log'])
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL,
        }
        level_name = self.config['log-level']
        level = levels.get(level_name.lower(), logging.DEBUG)
        logger.setLevel(level)
        logger.addHandler(handler)
        
        for pattern in self.config['trace']:
            tracing.trace_add_pattern(pattern)
        
    def run(self):
        self.pm.load_plugins()
        self.pm.enable_plugins()
        self.hooks.call('plugins-loaded')
        self.config.load()
        self.hooks.call('config-loaded')
        self.setup_logging()
        logging.info('Obnam %s starts' % obnamlib.version)
        if self.config.args:
            logging.info('Executing command: %s' % self.config.args[0])
            self.interp.execute(self.config.args[0], self.config.args[1:])
        else:
            raise obnamlib.AppException('Usage error: '
                                        'must give operation on command line')
        self.hooks.call('shutdown')
        logging.info('Obnam ends')

    def open_repository(self, create=False): # pragma: no cover
        repopath = self.config['repository']
        repofs = self.fsf.new(repopath, create=create)
        repofs.connect()
        return obnamlib.Repository(repofs, 
                                    self.config['node-size'],
                                    self.config['upload-queue-size'],
                                    self.config['lru-size'],
                                    self.hooks)

