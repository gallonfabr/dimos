# Copyright 2025-2026 Dimensional Inc.
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
"""Tests for SensorStore implementations."""

from dataclasses import dataclass
from pathlib import Path
import tempfile
import uuid

import pytest

from dimos.memory.sensor.base import InMemoryStore, SensorStore
from dimos.memory.sensor.pickledir import PickleDirStore
from dimos.memory.sensor.sqlite import SqliteStore
from dimos.types.timestamped import Timestamped


@dataclass
class SampleData(Timestamped):
    """Simple timestamped data for testing."""

    value: str

    def __init__(self, value: str, ts: float) -> None:
        super().__init__(ts)
        self.value = value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SampleData):
            return self.value == other.value and self.ts == other.ts
        return False


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file-based store tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def make_in_memory_store() -> SensorStore[SampleData]:
    return InMemoryStore[SampleData]()


def make_pickle_dir_store(tmpdir: str) -> SensorStore[SampleData]:
    return PickleDirStore[SampleData](tmpdir)


def make_sqlite_store(tmpdir: str) -> SensorStore[SampleData]:
    return SqliteStore[SampleData](Path(tmpdir) / "test.db")


# Base test data (always available)
testdata: list[tuple[object, str]] = [
    (lambda _: make_in_memory_store(), "InMemoryStore"),
    (lambda tmpdir: make_pickle_dir_store(tmpdir), "PickleDirStore"),
    (lambda tmpdir: make_sqlite_store(tmpdir), "SqliteStore"),
]

# Track postgres tables to clean up
_postgres_tables: list[str] = []

try:
    import psycopg2

    from dimos.memory.sensor.postgres import PostgresStore

    # Test connection
    _test_conn = psycopg2.connect(dbname="dimensional")
    _test_conn.close()

    def make_postgres_store(_tmpdir: str) -> SensorStore[SampleData]:
        """Create PostgresStore with unique table name."""
        table = f"test_{uuid.uuid4().hex[:8]}"
        _postgres_tables.append(table)
        store = PostgresStore[SampleData](table)
        store.start()
        return store

    testdata.append((lambda tmpdir: make_postgres_store(tmpdir), "PostgresStore"))

    @pytest.fixture(autouse=True)
    def cleanup_postgres_tables():
        """Clean up postgres test tables after each test."""
        yield
        if _postgres_tables:
            try:
                conn = psycopg2.connect(dbname="dimensional")
                conn.autocommit = True
                with conn.cursor() as cur:
                    for table in _postgres_tables:
                        cur.execute(f"DROP TABLE IF EXISTS {table}")
                conn.close()
            except Exception:
                pass  # Ignore cleanup errors
            _postgres_tables.clear()

except Exception:
    print("PostgreSQL not available")


@pytest.mark.parametrize("store_factory,store_name", testdata)
class TestSensorStore:
    """Parametrized tests for all SensorStore implementations."""

    def test_save_and_load(self, store_factory, store_name, temp_dir):
        store = store_factory(temp_dir)
        store.save(SampleData("data_at_1", 1.0))
        store.save(SampleData("data_at_2", 2.0))

        assert store.load(1.0) == SampleData("data_at_1", 1.0)
        assert store.load(2.0) == SampleData("data_at_2", 2.0)
        assert store.load(3.0) is None

    def test_find_closest_timestamp(self, store_factory, store_name, temp_dir):
        store = store_factory(temp_dir)
        store.save(SampleData("a", 1.0))
        store.save(SampleData("b", 2.0))
        store.save(SampleData("c", 3.0))

        # Exact match
        assert store._find_closest_timestamp(2.0) == 2.0

        # Closest to 1.4 is 1.0
        assert store._find_closest_timestamp(1.4) == 1.0

        # Closest to 1.6 is 2.0
        assert store._find_closest_timestamp(1.6) == 2.0

        # With tolerance
        assert store._find_closest_timestamp(1.4, tolerance=0.5) == 1.0
        assert store._find_closest_timestamp(1.4, tolerance=0.3) is None

    def test_iter_items(self, store_factory, store_name, temp_dir):
        store = store_factory(temp_dir)
        store.save(SampleData("a", 1.0))
        store.save(SampleData("c", 3.0))
        store.save(SampleData("b", 2.0))

        # Should iterate in timestamp order
        items = list(store._iter_items())
        assert items == [
            (1.0, SampleData("a", 1.0)),
            (2.0, SampleData("b", 2.0)),
            (3.0, SampleData("c", 3.0)),
        ]

    def test_iter_items_with_range(self, store_factory, store_name, temp_dir):
        store = store_factory(temp_dir)
        store.save(SampleData("a", 1.0))
        store.save(SampleData("b", 2.0))
        store.save(SampleData("c", 3.0))
        store.save(SampleData("d", 4.0))

        # Start only
        items = list(store._iter_items(start=2.0))
        assert items == [
            (2.0, SampleData("b", 2.0)),
            (3.0, SampleData("c", 3.0)),
            (4.0, SampleData("d", 4.0)),
        ]

        # End only
        items = list(store._iter_items(end=3.0))
        assert items == [(1.0, SampleData("a", 1.0)), (2.0, SampleData("b", 2.0))]

        # Both
        items = list(store._iter_items(start=2.0, end=4.0))
        assert items == [(2.0, SampleData("b", 2.0)), (3.0, SampleData("c", 3.0))]

    def test_empty_store(self, store_factory, store_name, temp_dir):
        store = store_factory(temp_dir)

        assert store.load(1.0) is None
        assert store._find_closest_timestamp(1.0) is None
        assert list(store._iter_items()) == []
