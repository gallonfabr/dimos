# Copyright 2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared fixtures for memory2 tests."""

from __future__ import annotations

import sqlite3
import tempfile
from typing import TYPE_CHECKING

import pytest

from dimos.memory2.blobstore.file import FileBlobStore
from dimos.memory2.blobstore.sqlite import SqliteBlobStore
from dimos.memory2.impl.memory import MemoryStore
from dimos.memory2.impl.sqlite import SqliteStore

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from dimos.memory2.backend import BlobStore
    from dimos.memory2.impl.memory import MemorySession
    from dimos.memory2.store import Session


# ── Stores ────────────────────────────────────────────────────────


@pytest.fixture
def memory_store() -> Generator[MemoryStore, None, None]:
    with MemoryStore() as store:
        yield store


@pytest.fixture
def memory_session(memory_store: MemoryStore) -> Generator[MemorySession, None, None]:
    with memory_store.session() as session:
        yield session


@pytest.fixture
def sqlite_store() -> Generator[SqliteStore, None, None]:
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        store = SqliteStore(path=f.name)
        with store:
            yield store


@pytest.fixture
def sqlite_session(sqlite_store: SqliteStore) -> Generator[Session, None, None]:
    with sqlite_store.session() as session:
        yield session


@pytest.fixture(params=["memory_session", "sqlite_session"])
def session(request: pytest.FixtureRequest) -> Session:
    return request.getfixturevalue(request.param)


# ── Blob Stores ───────────────────────────────────────────────────


@pytest.fixture
def file_blob_store(tmp_path: Path) -> Generator[FileBlobStore, None, None]:
    store = FileBlobStore(tmp_path / "blobs")
    store.start()
    yield store
    store.stop()


@pytest.fixture
def sqlite_blob_store() -> Generator[SqliteBlobStore, None, None]:
    conn = sqlite3.connect(":memory:")
    store = SqliteBlobStore(conn)
    store.start()
    yield store
    store.stop()
    conn.close()


@pytest.fixture(params=["file_blob_store", "sqlite_blob_store"])
def blob_store(request: pytest.FixtureRequest) -> BlobStore:
    return request.getfixturevalue(request.param)
