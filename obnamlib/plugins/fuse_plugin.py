# Copyright (C) 2013-2016  Valery Yundin
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
import stat
import logging
import errno
import struct

try:
    import fuse
    fuse.fuse_python_api = (0, 2)
except ImportError:
    # This is a workaround to allow us to fake a fuse module, so that
    # this plugin file can be imported. If the module isn't there, the
    # plugin won't work, and it will tell the user it won't work, but
    # at least Obnam won't crash at startup.
    class Bunch(object):
        def __init__(self, **kwds):
            self.__dict__.update(kwds)
    fuse = Bunch(Fuse=object)

import tracing

import obnamlib


class FileNotFoundError(obnamlib.ObnamError):

    msg = 'FUSE: File not found: {filename}'


class FuseModuleNotFoundError(obnamlib.ObnamError):

    msg = 'Failed to load module "fuse", try installing python-fuse'


class ObnamFuseOptParse(object):

    '''Option parsing class for FUSE.'''

    # NOTE: This class MUST set self.fuse_args.mountpoint.

    obnam = None

    def __init__(self, *args, **kw):
        if 'fuse_args' in kw:
            self.fuse_args = kw.pop('fuse_args')
        else:
            self.fuse_args = fuse.FuseArgs()
        if 'fuse' in kw:
            self.fuse = kw.pop('fuse')

    def parse_args(self, args=None, values=None):
        self.fuse_args.mountpoint = self.obnam.app.settings['to']
        for opt in self.obnam.app.settings['fuse-opt']:
            if opt == '-f':
                self.fuse_args.setmod('foreground')
            else:
                self.fuse_args.add(opt)
        if not hasattr(self.fuse_args, 'ro'):
            self.fuse_args.add('ro')


class ObnamFuseFile(object):

    fuse_fs = None  # points to active ObnamFuse object

    direct_io = False   # do not use direct I/O on this file.
    keep_cache = True   # cached file data need not to be invalidated.

    # Flags that indicate the caller wants to write to the file.
    # Since we're read-only, we'll have to fail the request.
    write_flags = (
        os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_TRUNC |
        os.O_APPEND)

    def __init__(self, path, flags, *mode):
        tracing.trace('path=%r', path)
        tracing.trace('flags=%r', flags)
        tracing.trace('mode=%r', mode)

        self.path = path

        if flags & self.write_flags:
            raise IOError(errno.EROFS, 'Read only filesystem')

        self.reading_pid = path == '/.pid'
        if self.reading_pid:
            return

        try:
            self.metadata = self.fuse_fs.get_metadata_in_generation(path)
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

        # if not a regular file return EINVAL
        if not stat.S_ISREG(self.metadata.st_mode):
            raise IOError(errno.EINVAL, 'Invalid argument')

    def read(self, length, offset):
        if self.reading_pid:
            return self.read_pid(length, offset)
        else:
            return self.read_data(length, offset)

    def release(self, flags):
        if self.reading_pid:
            return self.release_pid(flags)
        else:
            return self.release_data(flags)

    def read_pid(self, length, offset):
        tracing.trace('length=%r', length)
        tracing.trace('offset=%r', offset)
        pid = str(os.getpid())
        if length < len(pid) or offset != 0:
            return ''
        else:
            return pid

    def release_pid(self, flags):
        self.fuse_fs.root_refresh()
        return 0

    def fgetattr(self):
        tracing.trace('called')
        return self.fuse_fs.getattr(self.path)

    def read_data(self, length, offset):
        tracing.trace('self.path=%r', self.path)
        tracing.trace('length=%r', length)
        tracing.trace('offset=%r', offset)

        if length == 0 or offset >= self.metadata.st_size:
            return ''

        gen, repopath = self.fuse_fs.get_gen_path(self.path)

        # The file has a list of chunks, and we need to find the right
        # ones and return data from them. Note that we can't compute a
        # seek: there is no guarantee all the chunks are of the same
        # size. The user may have changed the chunk size setting
        # between each backup run. Thus, we have to iterate over the
        # list of chunk ids for the file, until we find the right
        # place.
        #
        # This is, obviously, not good for performance.
        #
        # Note that previous code here did the wrong thing by assuming
        # the chunk size was fixed, except for the last chunk for any
        # file.

        chunkids = self.fuse_fs.obnam.repo.get_file_chunk_ids(gen, repopath)
        output = []
        output_length = 0
        chunk_pos_in_file = 0
        size_cache = self.fuse_fs.obnam.chunk_sizes

        for chunkid in chunkids:
            if chunkid in size_cache:
                # Don't read the contents of the chunk until later,
                # in case it can be skipped completely.
                contents = None
            else:
                contents = self.fuse_fs.obnam.repo.get_chunk_content(chunkid)
                size_cache[chunkid] = len(contents)
            size = size_cache[chunkid]

            if chunk_pos_in_file + size > offset + output_length:
                start = offset + output_length - chunk_pos_in_file
                n = min(length - output_length, size - start)
                if contents is None:
                    contents = self.fuse_fs.obnam.repo.get_chunk_content(
                        chunkid)
                output.append(contents[start:start+n])
                output_length += n
                assert output_length <= length
                if output_length == length:
                    break
            chunk_pos_in_file += size

        return ''.join(output)

    def release_data(self, flags):
        tracing.trace('flags=%r', flags)
        return 0

    def fsync(self, isfsyncfile):
        tracing.trace('called')
        return 0

    def flush(self):
        tracing.trace('called')
        return 0

    def ftruncate(self, size):
        tracing.trace('size=%r', size)
        return 0

    def lock(self, cmd, owner, **kw):
        tracing.trace('cmd=%r', cmd)
        tracing.trace('owner=%r', owner)
        tracing.trace('kw=%r', kw)
        raise IOError(errno.EOPNOTSUPP, 'Operation not supported')


class ObnamFuse(fuse.Fuse):

    '''FUSE main class.'''

    def __init__(self, *args, **kw):
        self.obnam = kw['obnam']
        ObnamFuseFile.fuse_fs = self
        self.file_class = ObnamFuseFile
        self.init_root()
        fuse.Fuse.__init__(self, *args, **kw)

    def init_root(self):
        # we need the list of all real (non-checkpoint) generations
        client_name = self.obnam.app.settings['client-name']
        generations = [
            gen
            for gen in self.obnam.repo.get_client_generation_ids(client_name)
            if not self.obnam.repo.get_generation_key(
                gen, obnamlib.REPO_GENERATION_IS_CHECKPOINT)]

        # self.rootlist holds the stat information for each entry at
        # the root of the FUSE filesystem: /.pid, /latest, and one for
        # each generation.
        self.rootlist = {}

        used_generations = []
        for gen in generations:
            genspec = self.obnam.repo.make_generation_spec(gen)
            path = '/' + genspec
            try:
                genstat = self.get_stat_in_generation(path)
                end = self.obnam.repo.get_generation_key(
                    gen, obnamlib.REPO_GENERATION_ENDED)
                genstat.st_ctime = genstat.st_mtime = end
                self.rootlist[path] = genstat
                used_generations.append(gen)
            except obnamlib.ObnamError as e:
                logging.warning('Ignoring error %s', str(e))

        assert used_generations

        # self.rootstat is the stat information for the root of the
        # FUSE filesystem. We set it to the same as that of the latest
        # generation.
        latest_gen_id = used_generations[-1]
        latest_gen_spec = self.obnam.repo.make_generation_spec(latest_gen_id)
        latest_gen_root_stat = self.rootlist['/' + latest_gen_spec]
        self.rootstat = fuse.Stat(**latest_gen_root_stat.__dict__)

        # Add an entry for /latest to self.rootlist.
        symlink_stat = fuse.Stat(
            target=latest_gen_spec,
            **latest_gen_root_stat.__dict__)
        symlink_stat.st_mode &= ~(stat.S_IFDIR | stat.S_IFREG)
        symlink_stat.st_mode |= stat.S_IFLNK
        self.rootlist['/latest'] = symlink_stat

        # Add an entry for /.pid to self.rootlist.
        pidstat = fuse.Stat(**self.rootstat.__dict__)
        pidstat.st_mode = (
            stat.S_IFREG | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        self.rootlist['/.pid'] = pidstat

    def root_refresh(self):
        tracing.trace('called')
        self.obnam.reopen()
        self.init_root()

    def get_metadata_in_generation(self, path):
        tracing.trace('path=%r', path)

        gen, filename = self.get_gen_path(path)
        metadata = self.obnam.repo.get_metadata_from_file_keys(gen, filename)

        # FUSE does not allow negative timestamps, truncate to zero
        if metadata.st_atime_sec < 0:
            metadata.st_atime_sec = 0
        if metadata.st_mtime_sec < 0:
            metadata.st_mtime_sec = 0

        return metadata

    def get_stat_in_generation(self, path):
        tracing.trace('path=%r', path)
        metadata = self.get_metadata_in_generation(path)
        st = fuse.Stat()
        st.st_mode = metadata.st_mode
        st.st_dev = metadata.st_dev
        st.st_nlink = metadata.st_nlink
        st.st_uid = metadata.st_uid
        st.st_gid = metadata.st_gid
        st.st_size = metadata.st_size
        st.st_atime = metadata.st_atime_sec
        st.st_mtime = metadata.st_mtime_sec
        st.st_ctime = st.st_mtime
        return st

    def get_gen_path(self, path):
        client_name = self.obnam.app.settings['client-name']
        if path.count('/') == 1:
            gen_spec = path[1:]
            gen_id = self.obnam.repo.interpret_generation_spec(
                client_name, gen_spec)
            return (gen_id, '/')
        else:
            gen_spec, repopath = path[1:].split('/', 1)
            gen_id = self.obnam.repo.interpret_generation_spec(
                client_name, gen_spec)
            return (gen_id, '/' + repopath)

    def getattr(self, path):
        try:
            if path.count('/') == 1:
                if path == '/':
                    return self.rootstat
                elif path in self.rootlist:
                    return self.rootlist[path]
                else:
                    raise FileNotFoundError(filename=path)
            else:
                return self.get_stat_in_generation(path)
        except obnamlib.ObnamError:
            raise IOError(errno.ENOENT, 'No such file or directory')
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

    def readdir(self, path, fh):
        tracing.trace('path=%r', path)
        tracing.trace('fh=%r', fh)
        try:
            if path == '/':
                listdir = [x[1:] for x in self.rootlist.keys()]
            else:
                listdir = [
                    os.path.basename(x)
                    for x in self.obnam.repo.get_file_children(
                        *self.get_gen_path(path))]
            return [fuse.Direntry(name) for name in ['.', '..'] + listdir]
        except obnamlib.ObnamError:
            raise IOError(errno.EINVAL, 'Invalid argument')
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

    def readlink(self, path):
        try:
            statdata = self.rootlist.get(path)
            if statdata and hasattr(statdata, 'target'):
                return statdata.target
            metadata = self.get_metadata_in_generation(path)
            if metadata.islink():
                return metadata.target
            else:
                raise IOError(errno.EINVAL, 'Invalid argument')
        except obnamlib.ObnamError:
            raise IOError(errno.ENOENT, 'No such file or directory')
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

    def statfs(self):
        tracing.trace('called')

        client_name = self.obnam.app.settings['client-name']

        total_data = sum(
            self.obnam.repo.get_generation_key(
                gen, obnamlib.REPO_GENERATION_TOTAL_DATA)
            for gen in self.obnam.repo.get_client_generation_ids(client_name))

        files = sum(
            self.obnam.repo.get_generation_key(
                gen, obnamlib.REPO_GENERATION_FILE_COUNT)
            for gen in self.obnam.repo.get_client_generation_ids(client_name))

        stv = fuse.StatVfs()
        stv.f_bsize = 65536
        stv.f_frsize = 0
        stv.f_blocks = total_data / 65536
        stv.f_bfree = 0
        stv.f_bavail = 0
        stv.f_files = files
        stv.f_ffree = 0
        stv.f_favail = 0
        stv.f_flag = 0
        stv.f_namemax = 255
        # raise OSError(errno.ENOSYS, 'Unimplemented')
        return stv

    def getxattr(self, path, name, size):
        tracing.trace('path=%r', path)
        tracing.trace('name=%r', name)
        tracing.trace('size=%r', size)

        try:
            gen_id, repopath = self.get_gen_path(path)
        except obnamlib.RepositoryClientHasNoGenerations:
            return ''
        except obnamlib.RepositoryGenerationDoesNotExist:
            return ''

        tracing.trace('gen_id=%r', gen_id)
        tracing.trace('repopath=%r', repopath)

        try:
            try:
                metadata = self.get_metadata_in_generation(path)
            except ValueError:
                return 0
            if not metadata.xattr:
                return 0
            blob = metadata.xattr
            sizesize = struct.calcsize('!Q')
            name_blob_size = struct.unpack('!Q', blob[:sizesize])[0]
            name_blob = blob[sizesize:sizesize + name_blob_size]
            name_list = name_blob.split('\0')[:-1]
            if name in name_list:
                value_blob = blob[sizesize + name_blob_size:]
                idx = name_list.index(name)
                fmt = '!' + 'Q' * len(name_list)
                lengths_size = sizesize * len(name_list)
                lengths_list = struct.unpack(fmt, value_blob[:lengths_size])
                if size == 0:
                    return lengths_list[idx]
                pos = lengths_size + sum(lengths_list[:idx])
                value = value_blob[pos:pos + lengths_list[idx]]
                return value
        except obnamlib.ObnamError:
            raise IOError(errno.ENOENT, 'No such file or directory')
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

    def listxattr(self, path, size):
        tracing.trace('path=%r', path)
        tracing.trace('size=%r', size)

        try:
            gen_id, repopath = self.get_gen_path(path)
        except obnamlib.RepositoryClientHasNoGenerations:
            return []
        except obnamlib.RepositoryGenerationDoesNotExist:
            return []

        tracing.trace('gen_id=%r', gen_id)
        tracing.trace('repopath=%r', repopath)

        try:
            metadata = self.get_metadata_in_generation(path)
            if not metadata.xattr:
                return 0
            blob = metadata.xattr
            sizesize = struct.calcsize('!Q')
            name_blob_size = struct.unpack('!Q', blob[:sizesize])[0]
            if size == 0:
                return name_blob_size
            name_blob = blob[sizesize:sizesize + name_blob_size]
            return name_blob.split('\0')[:-1]
        except obnamlib.ObnamError:
            raise IOError(errno.ENOENT, 'No such file or directory')
        except:
            logging.error('Unexpected exception', exc_info=True)
            raise

    def fsync(self, path, isFsyncFile):
        return 0

    def chmod(self, path, mode):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def chown(self, path, uid, gid):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def link(self, targetPath, linkPath):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def mkdir(self, path, mode):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def mknod(self, path, mode, dev):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def rename(self, oldPath, newPath):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def rmdir(self, path):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def symlink(self, targetPath, linkPath):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def truncate(self, path, size):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def unlink(self, path):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def utime(self, path, times):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def write(self, path, buf, offset):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def setxattr(self, path, name, val, flags):
        raise IOError(errno.EROFS, 'Read only filesystem')

    def removexattr(self, path, name):
        raise IOError(errno.EROFS, 'Read only filesystem')


class MountPlugin(obnamlib.ObnamPlugin):

    '''Mount backup repository as a user-space filesystem.

    At the moment only a specific generation can be mounted

    '''

    def enable(self):
        mount_group = obnamlib.option_group['mount'] = 'Mounting with FUSE'
        self.app.add_subcommand('mount', self.mount, arg_synopsis='[ROOT]')
        self.app.settings.string_list(
            ['fuse-opt'],
            'options to pass directly to Fuse',
            metavar='FUSE',
            group=mount_group)

    def mount(self, args):
        '''Mount a backup repository as a FUSE filesystem.

        This subcommand allows you to access backups in an Obnam
        backup repository as normal files and directories. Each
        backed up file or directory can be viewed directly, using
        a graphical file manager or command line tools.

        Example: To mount your backup repository:

        mkdir my-fuse
        obnam mount --to my-fuse

        You can then access the backup using commands such as these:

        ls -l my-fuse
        ls -l my-fuse/latest
        diff -u my-fuse/latest/home/liw/README ~/README

        You can also restore files by copying them from the
        my-fuse directory:

        cp -a my-fuse/12765/Maildir ~/Maildir.restored

        To un-mount:

        fusermount -u my-fuse

        '''

        if not hasattr(fuse, 'fuse_python_api'):
            raise FuseModuleNotFoundError()
        self.app.settings.require('repository')
        self.app.settings.require('client-name')
        self.app.settings.require('to')

        # Remember the current working directory. FUSE will change
        # the current working directory to / when it backgrounds itself,
        # and this can break a --repository setting value that is a
        # relative pathname. When we re-open the repository, we'll first
        # chdir to where we are now, so this doesn't break.
        self.cwd = os.getcwd()

        self.repo = self.app.get_repository_object()

        logging.debug(
            'FUSE Mounting %s@%s:/ to %s',
            self.app.settings['client-name'],
            self.app.settings['generation'],
            self.app.settings['to'])

        # For speed, we need to remember how large each chunk is.
        # We store it here in the plugin so the cache survives a
        # re-open.
        self.chunk_sizes = {}

        ObnamFuseOptParse.obnam = self
        fuse_fs = ObnamFuse(obnam=self, parser_class=ObnamFuseOptParse)
        fuse_fs.flags = 0
        fuse_fs.multithreaded = 0
        fuse_fs.parse()
        fuse_fs.main()

        self.repo.close()

    def reopen(self):
        self.repo.close()

        # Change to original working directory, to allow relative paths
        # for --repository to work correctly.
        os.chdir(self.cwd)

        self.repo = self.app.get_repository_object()
