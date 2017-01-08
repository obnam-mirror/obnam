# Copyright 2011-2017  Lars Wirzenius
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


import os
import shutil
import subprocess
import tempfile
import tracing

import obnamlib


class EncryptionError(obnamlib.ObnamError):

    pass


class GpgError(EncryptionError):

    msg = ('gpg failed with exit code {returncode}\n'
           'Command: {command}\n{stderr}')


def generate_symmetric_key(numbits, filename='/dev/random'):
    '''Generate a random key of at least numbits for symmetric encryption.'''

    tracing.trace('numbits=%d', numbits)

    count = (numbits + 7) / 8
    f = open(filename, 'rb')
    key = f.read(count)
    f.close()

    return key.encode('hex')


class SymmetricKeyCache(object):

    '''Cache symmetric keys in memory.'''

    def __init__(self):
        self.clear()

    def get(self, repo, toplevel):
        if repo in self.repos and toplevel in self.repos[repo]:
            return self.repos[repo][toplevel]
        return None

    def put(self, repo, toplevel, key):
        if repo not in self.repos:
            self.repos[repo] = {}
        self.repos[repo][toplevel] = key

    def clear(self):
        self.repos = {}


def _gpg_pipe(args, data, passphrase, gpghome=None):
    '''Pipe things through gpg.

    With the right args, this can be either an encryption or a decryption
    operation.

    For safety, we give the passphrase to gpg via a file descriptor.
    The argument list is modified to include the relevant options for that.

    The data is fed to gpg via a temporary file, readable only by
    the owner, to avoid congested pipes.

    '''

    # Open pipe for passphrase, and write it there. If passphrase is
    # very long (more than 4 KiB by default), this might block. A better
    # implementation would be to have a loop around select(2) to do pipe
    # I/O when it can be done without blocking. Patches most welcome.

    keypipe = os.pipe()
    os.write(keypipe[1], passphrase + '\n')
    os.close(keypipe[1])

    try:
        out = _gpg(args + ['--passphrase-fd', str(keypipe[0])], stdin=data,
                   gpghome=gpghome)
    except:  # pragma: no cover
        os.close(keypipe[0])
        raise

    os.close(keypipe[0])

    return out


def encrypt_symmetric(cleartext, key, gpghome=None):
    '''Encrypt data with symmetric encryption.'''
    return _gpg_pipe(['-c'], cleartext, key, gpghome=gpghome)


def decrypt_symmetric(encrypted, key, gpghome=None):
    '''Decrypt encrypted data with symmetric encryption.'''
    return _gpg_pipe(['-d'], encrypted, key, gpghome=gpghome)


def _gpg(args, stdin='', gpghome=None):
    '''Run gpg and return its output.'''

    env = dict()
    env.update(os.environ)
    if gpghome is not None:
        env['GNUPGHOME'] = gpghome
        tracing.trace('gpghome=%s' % gpghome)

    argv = ['gpg', '-q', '--batch', '--no-textmode'] + args
    tracing.trace('argv=%s', repr(argv))
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env)
    out, err = p.communicate(stdin)

    # Return output data, or deal with errors.
    if p.returncode:  # pragma: no cover
        command = ' '.join(argv)
        raise GpgError(command=command, returncode=p.returncode, stderr=err)

    return out


def get_public_key(keyid, gpghome=None):
    '''Return the ASCII armored export form of a given public key.'''
    return _gpg(['--export', '--armor', keyid], gpghome=gpghome)


def get_public_key_user_ids(keyid, gpghome=None):  # pragma: no cover
    '''Return the ASCII armored export form of a given public key.'''
    user_ids = []
    output = _gpg(['--with-colons', '--list-keys', keyid], gpghome=gpghome)
    for line in output.splitlines():
        token = line.split(":")
        if len(token) >= 10:
            user_id = token[9].strip().replace(r'\x3a', ":")
            if user_id:
                user_ids.append(user_id)
    return user_ids


class Keyring(object):

    '''A simplistic representation of GnuPG keyrings.

    Just enough functionality for obnam's purposes.

    '''

    _keyring_name = 'pubring.gpg'

    def __init__(self, encoded=''):
        self._encoded = encoded
        self._gpghome = None
        self._keyids = None

    def _setup(self):
        self._gpghome = tempfile.mkdtemp()
        f = open(self._keyring, 'wb')
        f.write(self._encoded)
        f.close()
        _gpg(['--import-ownertrust'], stdin='''\
# List of assigned trustvalues, created Sun 01 Dec 2013 19:13:26 GMT
# (Use "gpg --import-ownertrust" to restore them)
''', gpghome=self._gpghome)

    def _cleanup(self):
        shutil.rmtree(self._gpghome, ignore_errors=True)
        self._gpghome = None

    @property
    def _keyring(self):
        return os.path.join(self._gpghome, self._keyring_name)

    def _real_keyids(self):
        output = self.gpg(False, ['--list-keys', '--with-colons'])

        keyids = []
        for line in output.splitlines():
            fields = line.split(':')
            if len(fields) >= 5 and fields[0] == 'pub':
                keyids.append(fields[4])
        return keyids

    def keyids(self):
        if self._keyids is None:
            self._keyids = self._real_keyids()
        return self._keyids

    def __str__(self):
        return self._encoded

    def __contains__(self, keyid):
        return keyid in self.keyids()

    def _reread_keyring(self):
        f = open(self._keyring, 'rb')
        self._encoded = f.read()
        f.close()
        self._keyids = None

    def add(self, key):
        self.gpg(True, ['--import'], stdin=key)

    def remove(self, keyid):
        self.gpg(True, ['--delete-key', '--yes', keyid])

    def gpg(self, reread, *args, **kwargs):
        self._setup()
        kwargs['gpghome'] = self._gpghome
        try:
            result = _gpg(*args, **kwargs)
        except BaseException:  # pragma: no cover
            self._cleanup()
            raise
        else:
            if reread:
                self._reread_keyring()
            self._cleanup()
            return result


class SecretKeyring(Keyring):

    '''Same as Keyring, but for secret keys.'''

    _keyring_name = 'secring.gpg'

    def _real_keyids(self):
        output = self.gpg(False, ['--list-secret-keys', '--with-colons'])

        keyids = []
        for line in output.splitlines():
            fields = line.split(':')
            if len(fields) >= 5 and fields[0] == 'sec':
                keyids.append(fields[4])
        return keyids


def encrypt_with_keyring(cleartext, keyring):
    '''Encrypt data with all keys in a keyring.'''
    recipients = []
    for keyid in keyring.keyids():
        recipients += ['-r', keyid]

    opts = [
        '-e',
        '--trust-model', 'always',
        '--no-encrypt-to',
        '--no-default-recipient',
    ]
    return keyring.gpg(False, opts + recipients, stdin=cleartext)


def decrypt_with_secret_keys(encrypted, gpghome=None):
    '''Decrypt data using secret keys GnuPG finds on its own.'''
    return _gpg(['-d'], stdin=encrypted, gpghome=gpghome)
