# Copyright (C) 2009-2016  Lars Wirzenius
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


import errno
import grp
import logging
import os
import pwd
import stat
import struct
import sys
import tracing

import obnamlib


metadata_verify_fields = (
    'st_mode', 'st_mtime_sec', 'st_mtime_nsec',
    'st_nlink', 'st_size', 'st_uid', 'groupname', 'username', 'target',
    'xattr',
)
metadata_fields = metadata_verify_fields + (
    'st_blocks', 'st_dev', 'st_gid', 'st_ino', 'st_atime_sec',
    'st_atime_nsec', 'md5', 'sha224', 'sha256', 'sha384', 'sha512', 'test',
)


class Metadata(object):

    '''Represent metadata for a filesystem entry.

    The metadata for a filesystem entry (file, directory, device, ...)
    consists of its stat(2) result, plus ACL and xattr.

    This class represents them as fields.

    We do not store all stat(2) fields. Here's a commentary on all fields:

        field?          stored? why

        st_atime_sec    yes     mutt compares atime, mtime to see ifmsg is new
        st_atime_nsec   yes     mutt compares atime, mtime to see ifmsg is new
        st_blksize      no      no way to restore, not useful backed up
        st_blocks       yes     should restore create holes in file?
        st_ctime        no      no way to restore, not useful backed up
        st_dev          yes     used to restore hardlinks
        st_gid          yes     used to restore group ownership
        st_ino          yes     used to restore hardlinks
        st_mode         yes     used to restore permissions
        st_mtime_sec    yes     used to restore mtime
        st_mtime_nsec   yes     used to restore mtime
        st_nlink        yes     used to restore hardlinks
        st_rdev         no      no use (correct me if I'm wrong about this)
        st_size         yes     user needs it to see size of file in backup
        st_uid          yes     used to restored ownership

    The field 'target' stores the target of a symlink.

    Additionally, the fields 'groupname' and 'username' are stored. They
    contain the textual names that correspond to st_gid and st_uid. When
    restoring, the names will be preferred by default.

    The 'md5' field optionally stores the whole-file checksum for the file.

    The 'xattr' field optionally stores extended attributes encoded as
    a binary blob.

    '''

    def __init__(self, **kwargs):
        obnamlib.object_created(self)
        self.md5 = None  # Silence pylint.
        self.st_size = None  # Silence pylint.
        self.st_mode = None  # Silence pylint.
        self.st_uid = None  # Silence pylint.
        self.st_gid = None  # Silence pylint.
        for field in metadata_fields:
            setattr(self, field, None)
        for field, value in kwargs.iteritems():
            setattr(self, field, value)

    def __del__(self):
        obnamlib.object_deleted(self, repr(self))

    def isdir(self):
        return self.st_mode is not None and stat.S_ISDIR(self.st_mode)

    def islink(self):
        return self.st_mode is not None and stat.S_ISLNK(self.st_mode)

    def isfile(self):
        return self.st_mode is not None and stat.S_ISREG(self.st_mode)

    def __repr__(self):  # pragma: no cover
        fields = ', '.join('%s=%s' % (k, getattr(self, k))
                           for k in metadata_fields)
        return 'Metadata(%s)' % fields

    def __cmp__(self, other):
        for field in metadata_fields:
            ours = getattr(self, field)
            theirs = getattr(other, field)
            if ours == theirs:
                continue
            if ours < theirs:
                return -1
            if ours > theirs:
                return +1
        return 0


# Caching versions of username/groupname lookups.
# These work on the assumption that the mappings from uid/gid do not
# change during the runtime of the backup.

_uid_to_username = {}


def _cached_getpwuid(uid):  # pragma: no cover
    if uid not in _uid_to_username:
        _uid_to_username[uid] = pwd.getpwuid(uid)
    return _uid_to_username[uid]


_gid_to_groupname = {}


def _cached_getgrgid(gid):  # pragma: no cover
    if gid not in _gid_to_groupname:
        _gid_to_groupname[gid] = grp.getgrgid(gid)
    return _gid_to_groupname[gid]


def get_xattrs_as_blob(fs, filename):  # pragma: no cover
    tracing.trace('filename=%s' % filename)

    try:
        names = fs.llistxattr(filename)
    except (OSError, IOError), e:
        if e.errno in (errno.EOPNOTSUPP, errno.EACCES):
            return None
        raise
    tracing.trace('names=%s' % repr(names))
    if not names:
        return None

    values = []
    for name in names[:]:
        tracing.trace('trying name %s' % repr(name))
        try:
            value = fs.lgetxattr(filename, name)
        except OSError, e:
            # On btrfs, at least, this can happen: the filesystem returns
            # a list of attribute names, but then fails when looking up
            # the value for one or more of the names. We pretend that the
            # name was never returned in that case.
            #
            # Obviously this can happen due to race conditions as well.
            if e.errno == errno.ENODATA:
                names.remove(name)
                logging.warning(
                    '%s has extended attribute named %s without value, '
                    'ignoring attribute',
                    filename, name)
            else:
                raise
        else:
            tracing.trace('lgetxattr(%s)=%s' % (name, value))
            values.append(value)
    assert len(names) == len(values)

    name_blob = ''.join('%s\0' % name for name in names)

    lengths = [len(v) for v in values]
    fmt = '!' + 'Q' * len(values)
    value_blob = struct.pack(fmt, *lengths) + ''.join(values)

    return ('%s%s%s' %
            (struct.pack('!Q', len(name_blob)),
             name_blob,
             value_blob))


def set_xattrs_from_blob(fs, filename, blob, user_only):  # pragma: no cover
    sizesize = struct.calcsize('!Q')
    name_blob_size = struct.unpack('!Q', blob[:sizesize])[0]
    name_blob = blob[sizesize:sizesize + name_blob_size]
    value_blob = blob[sizesize + name_blob_size:]

    names = [s for s in name_blob.split('\0')[:-1]]
    fmt = '!' + 'Q' * len(names)
    lengths_size = sizesize * len(names)
    lengths = struct.unpack(fmt, value_blob[:lengths_size])

    pos = lengths_size
    for i, name in enumerate(names):
        value = value_blob[pos:pos + lengths[i]]
        pos += lengths[i]
        if not user_only or name.startswith('user.'):
            fs.lsetxattr(filename, name, value)
        else:
            logging.warning(
                '%s: Not setting extended attribute %s due to not being root',
                filename, name)


def read_metadata(fs, filename, st=None, getpwuid=None, getgrgid=None):
    '''Return object detailing metadata for a filesystem entry.'''
    metadata = Metadata()
    stat_result = st or fs.lstat(filename)
    for field in metadata_fields:
        if field.startswith('st_') and hasattr(stat_result, field):
            setattr(metadata, field, getattr(stat_result, field))

    if stat.S_ISLNK(stat_result.st_mode):
        metadata.target = fs.readlink(filename)
    else:
        metadata.target = ''

    getgrgid = getgrgid or _cached_getgrgid
    try:
        metadata.groupname = getgrgid(metadata.st_gid)[0]
    except KeyError:
        metadata.groupname = None

    getpwuid = getpwuid or _cached_getpwuid
    try:
        metadata.username = getpwuid(metadata.st_uid)[0]
    except KeyError:
        metadata.username = None

    metadata.xattr = get_xattrs_as_blob(fs, filename)

    return metadata


class SetMetadataError(obnamlib.ObnamError):

    msg = "{filename}: Couldn't set metadata {metadata}: {errno}: {strerror}"


def _set_something(filename, what, func):  # pragma: no cover
    try:
        func()
    except OSError as e:
        logging.error(str(e), exc_info=True)
        raise SetMetadataError(
            filename=filename,
            metadata=what,
            errno=e.errno,
            strerror=e.strerror)


def set_metadata(fs, filename, metadata,
                 getuid=None, always_set_id_bits=False):
    '''Set metadata for a filesystem entry.

    We only set metadata that can sensibly be set: st_atime, st_mode,
    st_mtime. We also attempt to set ownership st_uid, st_gid), if
    running as root, otherwise only st_gid is attempted ignoring failures.
    We ignore the username, groupname fields: we assume the caller
    will change st_uid, st_gid accordingly if they want to mess with
    things. This makes the user take care of error situations and
    looking up user preferences.

    Raise SetMetadataError if setting any metadata fails.

    '''

    symlink = stat.S_ISLNK(metadata.st_mode)
    if symlink:
        _set_something(
            filename, 'symlink target',
            lambda: fs.symlink(metadata.target, filename))

    # Set owner before mode, so that a setuid bit does not get reset.
    getuid = getuid or os.getuid
    if getuid() == 0:
        _set_something(
            filename, 'uid and gid',
            lambda: fs.lchown(filename, metadata.st_uid, metadata.st_gid))
    else:
        # normal users can set the group if they are in the group, try to
        # restore the group, ignoring any errors
        try:
            uid = -1  # no change to user
            fs.lchown(filename, uid, metadata.st_gid)
        except OSError:
            sys.exc_clear()

    # If we are not the owner, and not root, do not restore setuid/setgid,
    # unless explicitly told to do so.
    mode = metadata.st_mode
    set_id_bits = always_set_id_bits or (getuid() in (0, metadata.st_uid))
    if not set_id_bits:  # pragma: no cover
        mode = mode & (~stat.S_ISUID)
        mode = mode & (~stat.S_ISGID)
    if symlink:
        _set_something(
            filename, 'symlink chmod',
            lambda: fs.chmod_symlink(filename, mode))
    else:
        _set_something(
            filename, 'chmod',
            lambda: fs.chmod_not_symlink(filename, mode))

    if metadata.xattr:  # pragma: no cover
        user_only = getuid() != 0
        _set_something(
            filename, 'xattrs',
            lambda:
            set_xattrs_from_blob(fs, filename, metadata.xattr, user_only))

    _set_something(
        filename, 'timestamps',
        lambda:
        fs.lutimes(
            filename, metadata.st_atime_sec, metadata.st_atime_nsec,
            metadata.st_mtime_sec, metadata.st_mtime_nsec))
