# Copyright (C) 2011-2016  Lars Wirzenius
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

import obnamlib


class EncryptionPlugin(obnamlib.ObnamPlugin):

    def enable(self):
        encryption_group = obnamlib.option_group['encryption'] = 'Encryption'

        self.app.settings.string(
            ['encrypt-with'],
            'PGP key with which to encrypt data '
            'in the backup repository',
            group=encryption_group)
        self.app.settings.string(
            ['keyid'],
            'PGP key id to add to/remove from '
            'the backup repository',
            group=encryption_group)
        self.app.settings.boolean(
            ['weak-random'],
            'use /dev/urandom instead of /dev/random '
            'to generate symmetric keys',
            default=True,
            group=encryption_group)
        self.app.settings.boolean(
            ['key-details'],
            'show additional user IDs for all keys',
            group=encryption_group)
        self.app.settings.string(
            ['symmetric-key-bits'],
            'size of symmetric key, in bits',
            metavar='BITS',
            group=encryption_group)
        self.app.settings.string(
            ['gnupghome'],
            'home directory for GPG',
            metavar='HOMEDIR',
            group=encryption_group,
            default=None)

        self.tag = "encrypt1"

        hooks = [
            ('repository-toplevel-init', self.toplevel_init,
             obnamlib.Hook.DEFAULT_PRIORITY),
            ('repository-data', self,
             obnamlib.Hook.LATE_PRIORITY),
            ('repository-add-client', self.add_client,
             obnamlib.Hook.DEFAULT_PRIORITY),
        ]
        for name, callback, rev in hooks:
            self.app.hooks.add_callback(name, callback, rev)

        self._pubkey = None

        self.app.add_subcommand('client-keys', self.client_keys)
        self.app.add_subcommand('list-keys', self.list_keys)
        self.app.add_subcommand('list-toplevels', self.list_toplevels)
        self.app.add_subcommand(
            'add-key', self.add_key, arg_synopsis='[CLIENT-NAME]...')
        self.app.add_subcommand(
            'remove-key', self.remove_key, arg_synopsis='[CLIENT-NAME]...')
        self.app.add_subcommand('remove-client', self.remove_client,
                                arg_synopsis='[CLIENT-NAME]...')

        self._symkeys = obnamlib.SymmetricKeyCache()

    def disable(self):
        self._symkeys.clear()

    @property
    def keyid(self):
        return self.app.settings['encrypt-with']

    @property
    def pubkey(self):
        if self._pubkey is None:
            self._pubkey = obnamlib.get_public_key(self.keyid,
                                                   gpghome=self.gnupghome)
        return self._pubkey

    @property
    def devrandom(self):
        if self.app.settings['weak-random']:
            return '/dev/urandom'
        else:
            return '/dev/random'

    @property
    def gnupghome(self):
        return self.app.settings['gnupghome']

    @property
    def symmetric_key_bits(self):
        return int(self.app.settings['symmetric-key-bits'] or '256')

    def _write_file(self, repo, pathname, contents):
        repo.get_fs().write_file(pathname, contents)

    def _overwrite_file(self, repo, pathname, contents):
        repo.get_fs().overwrite_file(pathname, contents)

    def toplevel_init(self, repo, toplevel):
        '''Initialize a new toplevel for encryption.'''

        if not self.keyid:
            return

        pubkeys = obnamlib.Keyring()
        pubkeys.add(self.pubkey)

        symmetric_key = obnamlib.generate_symmetric_key(
            self.symmetric_key_bits, filename=self.devrandom)
        encrypted = obnamlib.encrypt_with_keyring(symmetric_key, pubkeys)
        self._write_file(repo, os.path.join(toplevel, 'key'), encrypted)

        encoded = str(pubkeys)
        encrypted = obnamlib.encrypt_symmetric(encoded, symmetric_key)
        self._write_file(repo, os.path.join(toplevel, 'userkeys'), encrypted)

    def filter_read(self, encrypted, repo, toplevel):
        symmetric_key = self.get_symmetric_key(repo, toplevel)
        return obnamlib.decrypt_symmetric(encrypted, symmetric_key,
                                          gpghome=self.gnupghome)

    def filter_write(self, cleartext, repo, toplevel):
        if not self.keyid:
            return cleartext
        symmetric_key = self.get_symmetric_key(repo, toplevel)
        return obnamlib.encrypt_symmetric(cleartext, symmetric_key,
                                          gpghome=self.gnupghome)

    def get_symmetric_key(self, repo, toplevel):
        key = self._symkeys.get(repo, toplevel)
        if key is None:
            encoded = repo.get_fs().cat(os.path.join(toplevel, 'key'))
            key = obnamlib.decrypt_with_secret_keys(encoded,
                                                    gpghome=self.gnupghome)
            self._symkeys.put(repo, toplevel, key)
        return key

    def read_keyring(self, repo, toplevel):
        encrypted = repo.get_fs().cat(os.path.join(toplevel, 'userkeys'))
        encoded = self.filter_read(encrypted, repo, toplevel)
        return obnamlib.Keyring(encoded=encoded)

    def write_keyring(self, repo, toplevel, keyring):
        encoded = str(keyring)
        encrypted = self.filter_write(encoded, repo, toplevel)
        pathname = os.path.join(toplevel, 'userkeys')
        self._overwrite_file(repo, pathname, encrypted)

    def add_to_userkeys(self, repo, toplevel, public_key):
        userkeys = self.read_keyring(repo, toplevel)
        userkeys.add(public_key)
        self.write_keyring(repo, toplevel, userkeys)

    def remove_from_userkeys(self, repo, toplevel, keyid):
        userkeys = self.read_keyring(repo, toplevel)
        if keyid in userkeys:
            logging.debug('removing key %s from %s', keyid, toplevel)
            userkeys.remove(keyid)
            self.write_keyring(repo, toplevel, userkeys)
        else:
            logging.debug(
                'unable to remove key %s from %s (not there)',
                keyid, toplevel)

    def rewrite_symmetric_key(self, repo, toplevel):
        symmetric_key = self.get_symmetric_key(repo, toplevel)
        userkeys = self.read_keyring(repo, toplevel)
        encrypted = obnamlib.encrypt_with_keyring(symmetric_key, userkeys)
        self._overwrite_file(repo, os.path.join(toplevel, 'key'), encrypted)

    def add_client(self, repository, client_name):
        repository.set_client_encryption_key_id(client_name, self.keyid)

    def quit_if_unencrypted(self):
        if self.app.settings['encrypt-with']:
            return False
        self.app.output.write('Warning: Encryption not in use.\n')
        self.app.output.write('(Use --encrypt-with to set key.)\n')
        return True

    def client_keys(self, args):
        '''List clients and their keys in the repository.'''
        if self.quit_if_unencrypted():
            return
        repo = self.app.get_repository_object()
        clients = repo.get_client_names()
        for client in clients:
            keyid = repo.get_client_encryption_key_id(client)
            if keyid is None:
                key_info = 'no key'
            else:
                key_info = self._get_key_string(keyid)
            print client, key_info

    def _find_keys_and_toplevels(self, repo):
        toplevels = repo.get_fs().listdir('.')
        keys = dict()
        tops = dict()
        for toplevel in [d for d in toplevels if d != 'metadata']:
            # skip files (e.g. 'lock') or empty directories
            if not repo.get_fs().exists(os.path.join(toplevel, 'key')):
                continue
            try:
                userkeys = self.read_keyring(repo, toplevel)
            except obnamlib.EncryptionError:
                # other client's toplevels are unreadable
                tops[toplevel] = []
                continue
            for keyid in userkeys.keyids():
                keys[keyid] = keys.get(keyid, []) + [toplevel]
                tops[toplevel] = tops.get(toplevel, []) + [keyid]
        return keys, tops

    def _get_key_string(self, keyid):
        verbose = self.app.settings['key-details']
        if verbose:
            user_ids = obnamlib.get_public_key_user_ids(keyid,
                                                        gpghome=self.gnupghome)
            if user_ids:
                return "%s (%s)" % (keyid, ", ".join(user_ids))
        return str(keyid)

    def list_keys(self, args):
        '''List keys and the repository toplevels they're used in.'''
        if self.quit_if_unencrypted():
            return
        repo = self.app.get_repository_object()
        keys, _ = self._find_keys_and_toplevels(repo)
        for keyid in keys:
            print 'key: %s' % self._get_key_string(keyid)
            for toplevel in keys[keyid]:
                print '  %s' % toplevel

    def list_toplevels(self, args):
        '''List repository toplevel directories and their keys.'''
        if self.quit_if_unencrypted():
            return
        repo = self.app.get_repository_object()
        _, tops = self._find_keys_and_toplevels(repo)
        for toplevel in tops:
            print 'toplevel: %s' % toplevel
            for keyid in tops[toplevel]:
                print '  %s' % self._get_key_string(keyid)

    def _find_clientdirs(self, repo, client_names):
        return [repo.get_client_extra_data_directory(client_name)
                for client_name in client_names]

    def add_key(self, args):
        '''Add a key to the repository.'''
        if self.quit_if_unencrypted():
            return
        self.app.settings.require('keyid')
        repo = self.app.get_repository_object()
        keyid = self.app.settings['keyid']
        key = obnamlib.get_public_key(keyid, gpghome=self.gnupghome)
        clients = self._find_clientdirs(repo, args)
        for toplevel in repo.get_shared_directories() + clients:
            self.add_to_userkeys(repo, toplevel, key)
            self.rewrite_symmetric_key(repo, toplevel)

    def remove_key(self, args):
        '''Remove a key from the repository.'''
        if self.quit_if_unencrypted():
            return
        self.app.settings.require('keyid')
        repo = self.app.get_repository_object()
        keyid = self.app.settings['keyid']
        clients = self._find_clientdirs(repo, args)
        for toplevel in repo.get_shared_directories() + clients:
            self.remove_from_userkeys(repo, toplevel, keyid)
            self.rewrite_symmetric_key(repo, toplevel)

    def remove_client(self, args):
        '''Remove client and its key from repository.'''
        if self.quit_if_unencrypted():
            return
        repo = self.app.get_repository_object()
        repo.lock_client_list()
        for client_name in args:
            logging.info('removing client %s', client_name)
            repo.remove_client(client_name)
        repo.commit_client_list()
        repo.unlock_client_list()
