# Copyright (C) 2009-2017  Lars Wirzenius
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


import cliapp


from .version import __version__, __version_info__
from .structurederror import StructuredError
from .structurederror_finder import find_structured_errors
from .obnamerror import ObnamError
from .defaults import (
    DEFAULT_NODE_SIZE,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_UPLOAD_QUEUE_SIZE,
    DEFAULT_LRU_SIZE,
    DEFAULT_CHUNKIDS_PER_GROUP,
    DEFAULT_NAGIOS_WARN_AGE,
    DEFAULT_NAGIOS_CRIT_AGE,
    DEFAULT_DIR_BAG_BYTES,
    DEFAULT_DIR_CACHE_BYTES,
    DEFAULT_CHUNK_CACHE_BYTES,
    DEFAULT_CHUNK_BAG_BYTES,

    IDPATH_DEPTH,
    IDPATH_BITS,
    IDPATH_SKIP,

    MAX_ID,
)


# Import _obnam if it is there. We need to be able to do things without
# it, especially at build time, while we're generating manual pages.
# If _obnam is not there, substitute a dummy that throws an exception
# if used.


try:
    import obnamlib._obnam
except ImportError:
    class DummyExtension(object):
        def __getattr__(self, name):
            raise Exception('Trying to use _obnam, but that was not found.')
    _obnam = DummyExtension()


from .sizeparse import SizeSyntaxError, UnitNameError, ByteSizeParser

from .encryption import (
    generate_symmetric_key,
    encrypt_symmetric,
    decrypt_symmetric,
    get_public_key,
    get_public_key_user_ids,
    Keyring,
    SecretKeyring,
    encrypt_with_keyring,
    decrypt_with_secret_keys,
    SymmetricKeyCache,
    EncryptionError,
    GpgError)

from .hooks import (
    Hook, MissingFilterError, NoFilterTagError, FilterHook, HookManager)
from .pluginbase import ObnamPlugin
from .vfs import (
    VirtualFileSystem,
    VfsFactory,
    VfsTests,
    LockFail,
    NEW_DIR_MODE,
    NEW_FILE_MODE)
from .vfs_local import LocalFS
from .fsck_work_item import WorkItem
from .repo_fs import RepositoryFS
from .lockmgr import LockManager
from .forget_policy import ForgetPolicy
from .app import App, ObnamIOError, ObnamSystemError
from .humanise import humanise_duration, humanise_size, humanise_speed
from .chunkid_token_map import ChunkIdTokenMap
from .pathname_excluder import PathnameExcluder
from .splitpath import split_pathname

from .obj_serialiser import serialise_object, deserialise_object
from .bag import Bag, BagIdNotSetError, make_object_id, parse_object_id
from .bag_store import BagStore, serialise_bag, deserialise_bag
from .blob_store import BlobStore

from .repo_factory import (
    RepositoryFactory,
    UnknownRepositoryFormat,
    UnknownRepositoryFormatWanted)
from .repo_interface import (
    RepositoryInterface,
    RepositoryInterfaceTests,
    RepositoryClientAlreadyExists,
    RepositoryClientDoesNotExist,
    RepositoryClientListNotLocked,
    RepositoryClientListLockingFailed,
    RepositoryClientLockingFailed,
    RepositoryClientNotLocked,
    RepositoryClientKeyNotAllowed,
    RepositoryClientGenerationUnfinished,
    RepositoryGenerationKeyNotAllowed,
    RepositoryGenerationDoesNotExist,
    RepositoryClientHasNoGenerations,
    RepositoryFileDoesNotExistInGeneration,
    RepositoryFileKeyNotAllowed,
    RepositoryChunkDoesNotExist,
    RepositoryChunkContentNotInIndexes,
    RepositoryChunkIndexesNotLocked,
    RepositoryChunkIndexesLockingFailed,
    repo_key_name,
    REPO_CLIENT_TEST_KEY,
    REPO_GENERATION_TEST_KEY,
    REPO_GENERATION_STARTED,
    REPO_GENERATION_ENDED,
    REPO_GENERATION_IS_CHECKPOINT,
    REPO_GENERATION_FILE_COUNT,
    REPO_GENERATION_TOTAL_DATA,
    REPO_GENERATION_INTEGER_KEYS,
    REPO_FILE_TEST_KEY,
    REPO_FILE_MODE,
    REPO_FILE_MTIME_SEC,
    REPO_FILE_MTIME_NSEC,
    REPO_FILE_ATIME_SEC,
    REPO_FILE_ATIME_NSEC,
    REPO_FILE_NLINK,
    REPO_FILE_SIZE,
    REPO_FILE_UID,
    REPO_FILE_USERNAME,
    REPO_FILE_GID,
    REPO_FILE_GROUPNAME,
    REPO_FILE_SYMLINK_TARGET,
    REPO_FILE_XATTR_BLOB,
    REPO_FILE_BLOCKS,
    REPO_FILE_DEV,
    REPO_FILE_INO,
    REPO_FILE_MD5,
    REPO_FILE_SHA224,
    REPO_FILE_SHA256,
    REPO_FILE_SHA384,
    REPO_FILE_SHA512,
    REPO_FILE_INTEGER_KEYS,
    metadata_file_key_mapping)

from .checksummer import (
    checksum_algorithms,
    get_checksum_algorithm,
    get_checksum_algorithm_name,
    get_checksum_algorithm_key,
)

from .whole_file_checksummer import WholeFileCheckSummer

from .delegator import RepositoryDelegator, GenerationId

from .backup_progress import BackupProgress


#
# Repository format green-albatross specific modules.
#

from .fmt_ga import (
    GREEN_ALBATROSS_VERSION,
    RepositoryFormatGA,
    GAClientList,
    GAClient,
    GADirectory,
    GAImmutableError,
    create_gadirectory_from_dict,
    GATree,
    GAChunkStore,
    GAChunkIndexes,
    InMemoryLeafStore,
    LeafStore,
    CowLeaf,
    CowTree,
    LeafList,
)


#
# Repository format 6 specific modules.
#

from .metadata import (
    Metadata,
    read_metadata,
    set_metadata,
    SetMetadataError,
    metadata_fields)
from .fmt_6.repo_fmt_6 import RepositoryFormat6
from .fmt_6.repo_tree import RepositoryTree
from .fmt_6.chunklist import ChunkList
from .fmt_6.clientlist import ClientList
from .fmt_6.checksumtree import ChecksumTree
from .fmt_6.clientmetadatatree import ClientMetadataTree


option_group = {
    'perf': 'Performance tweaking',
    'devel': 'Development of Obnam itself',
}


__all__ = locals()
