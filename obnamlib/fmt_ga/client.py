# Copyright 2015-2017  Lars Wirzenius
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
#
# =*= License: GPL-3+ =*=


import copy
import os
import stat

import obnamlib


class GAClient(object):

    _well_known_blob = 'root'

    def __init__(self, client_name):
        self._fs = None
        self._dirname = None
        self._client_name = client_name
        self._current_time = None
        self._default_checksum_algorithm = None
        self.clear()

    def clear(self):
        self._blob_store = None
        self._client_keys = GAKeys()
        self._generations = GAGenerationList()
        self._data_is_loaded = False
        self._dir_cache_size = obnamlib.DEFAULT_DIR_CACHE_BYTES
        self._dir_bag_size = obnamlib.DEFAULT_DIR_BAG_BYTES
        self._checksum_algorithm = None

    def set_current_time(self, current_time):
        self._current_time = current_time

    def set_fs(self, fs):
        self._fs = fs

    def set_default_checksum_algorithm(self, name):
        self._default_checksum_algorithm = name

    def get_client_checksum_key(self):
        self._load_data()
        assert self._checksum_algorithm is not None
        return obnamlib.get_checksum_algorithm_key(self._checksum_algorithm)

    def set_dir_bag_size(self, size):
        self._dir_bag_size = size
        if self._blob_store:
            self._blob_store.set_max_bag_size(self._dir_bag_size)

    def set_dir_cache_size(self, size):
        self._dir_cache_size = size
        if self._blob_store:
            self._blob_store.set_max_cache_bytes(self._dir_cache_size)

    def set_dirname(self, dirname):
        self._dirname = dirname

    def get_dirname(self):
        return self._dirname

    def flush(self):
        self._save_file_metadata()

    def flush_ro(self):
        for gen in self._generations:
            metadata = gen.get_file_metadata()
            metadata.flush_ro()
            gen.set_root_object_id(metadata.get_root_object_id())

    def commit(self):
        self._load_data()
        self._finish_current_generation_if_any()
        self._save_data()

    def _finish_current_generation_if_any(self):
        if self._generations:
            latest = self._generations.get_latest()
            key_name = obnamlib.repo_key_name(obnamlib.REPO_GENERATION_ENDED)
            if latest.get_key(key_name) is None:
                latest.set_key(key_name, int(self._current_time()))

    def _save_data(self):
        self._save_file_metadata()
        self._save_per_client_data()

    def _save_file_metadata(self):
        for gen in self._generations:
            metadata = gen.get_file_metadata()
            metadata.flush()
            gen.set_root_object_id(metadata.get_root_object_id())

    def _get_blob_store(self):
        if self._blob_store is None:
            bag_store = obnamlib.BagStore()
            bag_store.set_location(self._fs, self._dirname)

            self._blob_store = obnamlib.BlobStore()
            self._blob_store.set_bag_store(bag_store)
            self._blob_store.set_max_bag_size(self._dir_bag_size)
            self._blob_store.set_max_cache_bytes(self._dir_cache_size)
        return self._blob_store

    def _save_per_client_data(self):
        data = {
            'whole-file-checksum': self._checksum_algorithm,
            'keys': self._client_keys.as_dict(),
            'generations': [g.as_dict() for g in self._generations],
        }
        blob = obnamlib.serialise_object(data)
        blob_store = self._get_blob_store()
        blob_store.put_well_known_blob(self._well_known_blob, blob)

    def _load_data(self):
        if not self._data_is_loaded:
            self.clear()
            self._load_per_client_data()
            self._load_file_metadata()
            self._data_is_loaded = True

    def _load_per_client_data(self):
        blob_store = self._get_blob_store()
        blob = blob_store.get_well_known_blob(self._well_known_blob)
        if blob is None:
            self._checksum_algorithm = self._default_checksum_algorithm
        else:
            data = obnamlib.deserialise_object(blob)
            self._checksum_algorithm = data['whole-file-checksum']
            self._client_keys.set_from_dict(data['keys'])
            for gen_dict in data['generations']:
                gen = GAGeneration()
                gen.set_from_dict(gen_dict)
                self._generations.append(gen)

    def _load_file_metadata(self):
        blob_store = self._get_blob_store()
        for gen in self._generations:
            metadata = gen.get_file_metadata()
            metadata.set_blob_store(blob_store)
            metadata.set_root_object_id(gen.get_root_object_id())

    def get_client_generation_ids(self):
        self._load_data()
        return [
            obnamlib.GenerationId(self._client_name, gen.get_number())
            for gen in self._generations]

    def create_generation(self):
        self._load_data()
        self._require_previous_generation_is_finished()

        new_generation = GAGeneration()
        new_metadata = new_generation.get_file_metadata()
        new_metadata.set_blob_store(self._get_blob_store())

        if self._generations:
            latest = self._generations.get_latest()
            new_dict = copy.deepcopy(latest.as_dict())
            new_generation.set_from_dict(new_dict)

            latest_metadata = latest.get_file_metadata()
            new_metadata.set_root_object_id(
                latest_metadata.get_root_object_id())
        else:
            new_metadata.set_root_object_id(None)

        new_generation.set_number(self._new_generation_number())
        new_generation.set_key(
            obnamlib.repo_key_name(obnamlib.REPO_GENERATION_STARTED),
            int(self._current_time()))
        new_generation.set_key(
            obnamlib.repo_key_name(obnamlib.REPO_GENERATION_ENDED),
            None)

        self._generations.append(new_generation)

        return obnamlib.GenerationId(
            self._client_name, new_generation.get_number())

    def _require_previous_generation_is_finished(self):
        if self._generations:
            latest = self._generations.get_latest()
            key_name = obnamlib.repo_key_name(obnamlib.REPO_GENERATION_ENDED)
            if latest.get_key(key_name) is None:
                raise obnamlib.RepositoryClientGenerationUnfinished(
                    client_name=self._client_name)

    def _new_generation_number(self):
        if self._generations:
            ids = [gen.get_number() for gen in self._generations]
            return str(int(ids[-1]) + 1)
        else:
            return str(1)

    def remove_generation(self, gen_number):
        self._load_data()
        remaining = []
        removed = False

        for generation in self._generations:
            if generation.get_number() == gen_number:
                removed = True
            else:
                remaining.append(generation)

        if not removed:
            raise obnamlib.RepositoryGenerationDoesNotExist(
                client_name=self._client_name,
                gen_id=gen_number)

        import cliapp
        dumper = cliapp.MemoryProfileDumper({
            'dump-memory-profile': True,
            'memory-dump-interval': 0,
        })
        self._dumper = dumper

        chunks_to_remove = set(self._generate_generation_chunk_ids(gen_number))
        dumper.dump_memory_profile('after getting chunks in removed gen')

        for chunk_id in self._generate_chunk_ids_in_generations(remaining):
            if chunk_id in chunks_to_remove:
                chunks_to_remove.remove(chunk_id)
                if len(chunks_to_remove) == 0:
                    break
        dumper.dump_memory_profile('after computing chunk uniq to removed gen')

        self._generations.set_generations(remaining)

        return list(chunks_to_remove)

    def get_generation_key(self, gen_number, key):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        key_name = obnamlib.repo_key_name(key)
        if key in obnamlib.REPO_GENERATION_INTEGER_KEYS:
            value = generation.get_key(key_name)
            if value is None:
                value = 0
            return int(value)
        else:
            return generation.get_key(key_name, default='')

    def _lookup_generation_by_gen_number(self, gen_number):
        generation = self._generations.get_generation(gen_number)
        if generation is None:
            raise obnamlib.RepositoryGenerationDoesNotExist(
                gen_id=gen_number, client_name=self._client_name)
        return generation

    def set_generation_key(self, gen_number, key, value):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        generation.set_key(obnamlib.repo_key_name(key), value)

    def file_exists(self, gen_number, filename):
        self._load_data()
        try:
            generation = self._lookup_generation_by_gen_number(gen_number)
        except obnamlib.RepositoryGenerationDoesNotExist:
            return False
        metadata = generation.get_file_metadata()
        return metadata.file_exists(filename)

    def add_file(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        metadata.add_file(filename)

    def remove_file(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        metadata.remove_file(filename)

    def get_file_key(self, gen_number, filename, key):
        self._load_data()
        self._require_file_exists(gen_number, filename)
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()

        if key in obnamlib.REPO_FILE_INTEGER_KEYS:
            default = 0
        else:
            default = ''

        value = metadata.get_file_key(filename, key)
        if value is None:
            return default
        return value

    def _require_file_exists(self, gen_number, filename):
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        if not metadata.file_exists(filename):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)

    def get_metadata_from_file_keys(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata_obj = generation.get_file_metadata()
        if not metadata_obj.file_exists(filename):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)
        return metadata_obj.get_metadata_from_file_keys(filename)

    def set_file_key(self, gen_number, filename, key, value):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        if not metadata.set_file_key(filename, key, value):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)

    def set_file_keys_from_metadata(self, gen_number, filename, file_metadata):
        self._load_data()

        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        if not metadata.set_file_keys_from_metadata(filename, file_metadata):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)

    def get_file_chunk_ids(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        result = metadata.get_file_chunk_ids(filename)
        if result is None:
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)
        return result

    def append_file_chunk_id(self, gen_number, filename, chunk_id):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        if not metadata.append_file_chunk_id(filename, chunk_id):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)

    def clear_file_chunk_ids(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        if not metadata.clear_file_chunk_ids(filename):
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)

    def get_generation_chunk_ids(self, gen_number):
        return list(self._generate_generation_chunk_ids(gen_number))

    def _generate_generation_chunk_ids(self, gen_number):
        if hasattr(self, '_dumper'):
            dump = self._dumper.dump_memory_profile
        else:
            def dump(msg):
                return None

        self._load_data()

        generation = self._lookup_generation_by_gen_number(gen_number)

        metadata = generation.get_file_metadata()
        dump('after getting file metadata for generation')

        for filename in metadata:
            chunk_ids = metadata.get_file_chunk_ids(filename)
            for chunk_id in chunk_ids:
                yield chunk_id
        dump('after yielding all chunk ids')

    def _generate_chunk_ids_in_generations(self, generations):
        for generation in generations:
            gen_number = generation.get_number()
            for chunk_id in self._generate_generation_chunk_ids(gen_number):
                yield chunk_id

    def get_file_children(self, gen_number, filename):
        self._load_data()
        generation = self._lookup_generation_by_gen_number(gen_number)
        metadata = generation.get_file_metadata()
        result = metadata.get_file_children(filename)
        if result is None:
            raise obnamlib.RepositoryFileDoesNotExistInGeneration(
                client_name=self._client_name,
                genspec=gen_number,
                filename=filename)
        return result

    def _is_direct_child_of(self, child, parent):
        return os.path.dirname(child) == parent and child != parent


class GAKeys(object):

    def __init__(self):
        self._dict = {}

    def as_dict(self):
        return self._dict

    def set_from_dict(self, keys_dict):
        self._dict = keys_dict

    def get_key(self, key, default=None):
        return self._dict.get(key, default)

    def set_key(self, key, value):
        self._dict[key] = value


class GAGenerationList(object):

    def __init__(self):
        self._generations = []
        self._by_number = {}

    def __len__(self):
        return len(self._generations)

    def __iter__(self):
        for gen in self._generations[:]:
            yield gen

    def get_generation(self, gen_number):
        return self._by_number.get(gen_number)

    def get_latest(self):
        return self._generations[-1]

    def append(self, gen):
        self._generations.append(gen)
        self._by_number[gen.get_number()] = gen

    def set_generations(self, generations):
        self._generations = generations
        self._by_number = dict((gen.get_number(), gen) for gen in generations)


class GAGeneration(object):

    def __init__(self):
        self._id = None
        self._keys = GAKeys()
        self._file_metadata = GAFileMetadata()
        self._root_object_id = None

    def as_dict(self):
        return {
            'id': self._id,
            'keys': self._keys.as_dict(),
            'root_object_id': self._root_object_id,
        }

    def set_from_dict(self, data):
        self._id = data['id']
        self._keys = GAKeys()
        self._keys.set_from_dict(data['keys'])
        self._root_object_id = data['root_object_id']

    def get_number(self):
        return self._id

    def set_number(self, new_id):
        self._id = new_id

    def get_key(self, key, default=None):
        return self._keys.get_key(key, default=default)

    def set_key(self, key, value):
        self._keys.set_key(key, value)

    def get_root_object_id(self):
        return self._root_object_id

    def set_root_object_id(self, root_object_id):
        self._root_object_id = root_object_id

    def get_file_metadata(self):
        return self._file_metadata


class GAFileMetadata(object):

    def __init__(self):
        self._blob_store = None
        self._tree = None
        self._added_files = AddedFiles()

    def set_blob_store(self, blob_store):
        assert self._blob_store is None
        assert self._tree is None
        self._blob_store = blob_store

    def set_root_object_id(self, root_object_id):
        assert self._blob_store is not None
        assert self._tree is None
        self._tree = obnamlib.GATree()
        self._tree.set_blob_store(self._blob_store)
        self._tree.set_root_directory_id(root_object_id)

    def get_root_object_id(self):
        return self._tree.get_root_directory_id()

    def flush(self):
        assert len(self._added_files) == 0
        self._tree.flush()

    def flush_ro(self):
        self._tree.flush_ro()

    def __iter__(self):
        for filename in self._added_files:
            yield filename

        stack = ['/']
        while stack:
            dir_path = stack.pop()
            dir_obj = self._tree.get_directory(dir_path)
            if dir_obj is None:
                continue
            yield dir_path
            for basename in dir_obj.get_file_basenames():
                if basename != '.':
                    pathname = os.path.join(dir_path, basename)
                    yield pathname
            for basename in dir_obj.get_subdir_basenames():
                stack.append(os.path.join(dir_path, basename))

    def file_exists(self, filename):
        if filename in self._added_files:
            return True
        dir_obj, _, basename = self._get_dir_obj(filename)
        return dir_obj and basename in dir_obj.get_file_basenames()

    def _get_dir_obj(self, filename):
        '''Return GADirectory and basename for filename.

        If filename refers to an existing directory, the GADirectory
        for the directory, the path to the directory, and the basename
        "." are returned.

        If filename refers to a file in an existing directory, the
        GADirectory, the path to the directory, and the basename of
        the file are returned. Note that in this case it is always a
        file, never a subdirectory. The file need not exist yet.

        Otherwise, (None, None, None) is returned.

        '''

        dir_obj = self._tree.get_directory(filename)
        if dir_obj:
            return dir_obj, filename, '.'

        parent_path = os.path.dirname(filename)
        dir_obj = self._tree.get_directory(parent_path)
        if dir_obj:
            return dir_obj, parent_path, os.path.basename(filename)

        return None, None, None

    def add_file(self, filename):
        if not self.file_exists(filename):
            self._added_files.add_file(filename)

    def remove_file(self, filename):
        if filename in self._added_files:
            self._added_files.remove_file(filename)

        if filename == '/':
            self._tree.remove_directory('/')
        else:
            parent_path = os.path.dirname(filename)
            parent_obj = self._tree.get_directory(parent_path)
            if parent_obj:
                basename = os.path.basename(filename)
                parent_obj = self._make_mutable(parent_obj)
                parent_obj.remove_file(basename)
                parent_obj.remove_subdir(basename)
                self._tree.set_directory(parent_path, parent_obj)

    def get_file_key(self, filename, key):
        if filename in self._added_files:
            return self._added_files.get_file_key(filename, key)
        dir_obj, _, basename = self._get_dir_obj(filename)
        if dir_obj:
            return dir_obj.get_file_key(basename, key)
        else:
            return None

    def get_metadata_from_file_keys(self, filename):
        if filename in self._added_files:
            return self._make_metadata(
                lambda key: self._added_files.get_file_key(filename, key))
        else:
            dir_obj, _, basename = self._get_dir_obj(filename)
            # We've already verifed the file exists, so we don't need
            # to handle the case where dir_obj is None.
            assert dir_obj is not None

            return self._make_metadata(
                lambda key: dir_obj.get_file_key(basename, key))

    def _make_metadata(self, get_value):
        metadata = obnamlib.Metadata()

        for key, field in obnamlib.metadata_file_key_mapping:
            value = get_value(key)
            if value is None:
                if key in obnamlib.REPO_FILE_INTEGER_KEYS:
                    value = 0
                else:
                    value = ''
            setattr(metadata, field, value)

        return metadata

    def set_file_keys_from_metadata(self, filename, file_metadata):
        if filename in self._added_files:
            self._added_files.set_file_key(
                filename, obnamlib.REPO_FILE_MODE, file_metadata.st_mode)
            self._flush_added_file(filename)

        dir_obj, _, basename = self._get_dir_obj(filename)
        if dir_obj is None:
            return False

        for key, field in obnamlib.metadata_file_key_mapping:
            value = getattr(file_metadata, field)
            old_value = dir_obj.get_file_key(basename, key)
            if value != old_value:
                if not dir_obj.is_mutable():
                    dir_obj, basename = self._get_mutable_dir_obj(filename)
                dir_obj.set_file_key(basename, key, value)

        return True

    def set_file_key(self, filename, key, value):
        if filename in self._added_files:
            self._added_files.set_file_key(filename, key, value)
            if key == obnamlib.REPO_FILE_MODE:
                self._flush_added_file(filename)
            return True
        else:
            immutable, _, basename = self._get_dir_obj(filename)
            if not immutable:
                return False
            old_value = immutable.get_file_key(basename, key)
            if old_value != value:
                mutable, basename2 = self._get_mutable_dir_obj(filename)
                mutable.set_file_key(basename2, key, value)
        return True

    def _get_mutable_dir_obj(self, filename):
        dir_obj, dir_path, basename = self._get_dir_obj(filename)
        if dir_obj:
            if dir_obj.is_mutable():
                return dir_obj, basename
            else:
                new_obj = self._make_mutable(dir_obj)
                self._tree.set_directory(dir_path, new_obj)
                return new_obj, basename
        else:
            return dir_obj, basename

    def _make_mutable(self, dir_obj):
        if dir_obj.is_mutable():
            return dir_obj
        else:
            return obnamlib.create_gadirectory_from_dict(dir_obj.as_dict())

    def _flush_added_file(self, filename):
        mode = self._added_files.get_file_key(
            filename, obnamlib.REPO_FILE_MODE)
        assert mode is not None
        file_dict = self._added_files.get_file_dict(filename)
        if stat.S_ISDIR(mode):
            dir_obj = obnamlib.GADirectory()
            dir_obj.add_file('.')
            for key, value in file_dict['keys'].items():
                dir_obj.set_file_key('.', key, value)
            self._tree.set_directory(filename, dir_obj)
        else:
            basename = os.path.basename(filename)
            parent_path = os.path.dirname(filename)
            parent_obj = self._tree.get_directory(parent_path)
            if parent_obj is None:
                parent_obj = obnamlib.GADirectory()
                parent_obj.add_file('.')
            else:
                parent_obj = self._make_mutable(parent_obj)

            parent_obj.add_file(basename)
            for key, value in file_dict['keys'].items():
                parent_obj.set_file_key(basename, key, value)
            for chunk_id in file_dict['chunks']:
                parent_obj.append_file_chunk_id(basename, chunk_id)
            self._tree.set_directory(parent_path, parent_obj)

        self._added_files.remove_file(filename)

    def get_file_chunk_ids(self, filename):
        if filename in self._added_files:
            chunk_ids = self._added_files.get_file_chunk_ids(filename)
            return chunk_ids

        dir_obj, _, basename = self._get_dir_obj(filename)
        if dir_obj:
            chunk_ids = dir_obj.get_file_chunk_ids(basename)
            return chunk_ids
        else:
            return None

    def append_file_chunk_id(self, filename, chunk_id):
        if filename in self._added_files:
            self._added_files.append_file_chunk_id(filename, chunk_id)
            return True
        dir_obj, basename = self._get_mutable_dir_obj(filename)
        if dir_obj:
            dir_obj.append_file_chunk_id(basename, chunk_id)
            return True
        return False

    def clear_file_chunk_ids(self, filename):
        if filename in self._added_files:
            self._added_files.clear_file_chunk_ids(filename)
            return True
        dir_obj, basename = self._get_mutable_dir_obj(filename)
        assert basename != '.'
        if dir_obj:
            dir_obj.clear_file_chunk_ids(basename)
            return True
        return False

    def get_file_children(self, filename):
        assert filename not in self._added_files
        dir_obj, dirname, basename = self._get_dir_obj(filename)
        if basename != '.':
            return []
        if dir_obj:
            files = [x for x in dir_obj.get_file_basenames() if x != '.']
            subdirs = dir_obj.get_subdir_basenames()
            return [os.path.join(dirname, x) for x in files + subdirs]
        return None


class AddedFiles(object):

    def __init__(self):
        self.clear()

    def clear(self):
        self._files = {}

    def __contains__(self, filename):
        return filename in self._files

    def __iter__(self):
        for filename in self._files:
            yield filename

    def __len__(self):
        return len(self._files)

    def get_file_dict(self, filename):
        return self._files[filename]

    def add_file(self, filename):
        assert filename not in self._files
        self._files[filename] = {
            'keys': {},
            'chunks': [],
        }

    def remove_file(self, filename):
        assert filename in self._files
        del self._files[filename]

    def get_file_key(self, filename, key):
        return self._files[filename]['keys'].get(key)

    def set_file_key(self, filename, key, value):
        self._files[filename]['keys'][key] = value

    def get_file_chunk_ids(self, filename):
        return self._files[filename]['chunks']

    def append_file_chunk_id(self, filename, chunk_id):
        self._files[filename]['chunks'].append(chunk_id)

    def clear_file_chunk_ids(self, filename):
        self._files[filename]['chunks'] = []
