# Memory2 Implementation Plan

Source of truth: `plans/memory_2_spec_v_2.md`

## Context

PR #1080 introduced `TimeSeriesStore[T]` with pluggable backends. Paul's review identified it mixes DB lifecycle, connection, and query concerns. `memory.md` describes a system where all sensor data is stored as temporal streams with spatial indexing, cross-stream correlation, and multimodal search. The spec (`memory_2_spec_v_2.md`) defines the full public API. This plan maps the spec to concrete SQLite implementation in `dimos/memory2/`.

## File Structure

```
dimos/memory2/
    __init__.py              # public exports
    _sql.py                  # _validate_identifier(), SQL helpers
    types.py                 # ObservationRef, ObservationMeta, ObservationRow, Lineage, Pose (spec's own Pose)
    db.py                    # DB (Resource lifecycle, SqliteDB)
    session.py               # Session (connection, stream factory, correlate)
    stream.py                # Stream (append + QueryableObservationSet)
    observation_set.py       # ObservationSet (lazy, re-queryable, predicate/ref-table backed)
    query.py                 # Query (filter/search/rank/limit → fetch/fetch_set)
    test_memory2.py          # tests
```

## Implementation Priority (per spec §15)

### Phase 1: Core types + storage

1. **`types.py`** — Data classes

```python
@dataclass(frozen=True)
class ObservationRef:
    stream: str
    id: str

@dataclass
class Pose:
    xyz: tuple[float, float, float]
    quat_xyzw: tuple[float, float, float, float] | None = None

@dataclass
class ObservationMeta:
    ref: ObservationRef
    ts_start: float | None = None
    ts_end: float | None = None
    robot_id: str | None = None
    frame_id: str | None = None
    pose: Pose | None = None
    pose_source: str | None = None
    pose_confidence: float | None = None
    payload_codec: str | None = None
    payload_size_bytes: int | None = None
    tags: dict[str, Any] = field(default_factory=dict)

@dataclass
class ObservationRow:
    ref: ObservationRef
    ts_start: float | None = None
    ts_end: float | None = None
    pose: Pose | None = None
    scores: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Lineage:
    parents: list[str] = field(default_factory=list)
    parent_refs: list[ObservationRef] = field(default_factory=list)
    query_repr: str | None = None
```

Note: `Pose` here is the spec's lightweight tuple-based pose for storage/filtering. Conversion to/from DimOS `dimos.msgs.geometry_msgs.Pose` via helper:

```python
def to_storage_pose(p: DimOSPose | DimOSPoseStamped | Pose) -> Pose: ...
def to_dimos_pose(p: Pose) -> DimOSPose: ...
```

2. **`_sql.py`** — SQL helpers

```python
def validate_identifier(name: str) -> str: ...  # regex check, length limit
```

3. **`db.py`** — DB + SqliteDB

```python
class DB(Resource, ABC):
    def session(self) -> Session: ...
    def close(self) -> None: ...
    def start(self) -> None: pass
    def stop(self) -> None: self.close()
```

SqliteDB internals:
- Stores file path, creates parent dirs on connect
- `_connect()`: `sqlite3.connect()`, WAL mode, loads sqlite-vec (optional), loads FTS5
- Tracks sessions via `WeakSet` for cleanup
- `:memory:` uses `file::memory:?cache=shared` URI
- Thread safety: each session = one connection, no `check_same_thread=False`

4. **`session.py`** — Session + SqliteSession

```python
class Session(ABC):
    def stream(self, name: str, payload_type: type,
               capabilities: set[str], retention: str = "run",
               config: dict | None = None) -> Stream: ...
    def list_streams(self) -> list[str]: ...
    def execute(self, sql: str, params=()) -> list: ...
    def close(self) -> None: ...
    def __enter__ / __exit__
```

SqliteSession:
- Holds one `sqlite3.Connection`
- `stream()`: creates tables if needed (see schema below), caches Stream instances
- Registers stream metadata in a `_streams` registry table

### Phase 2: Stream + Query + ObservationSet

5. **`stream.py`** — Stream (implements `QueryableObservationSet`)

```python
class Stream(Generic[T]):
    # Write
    def append(self, payload: T, **meta: Any) -> ObservationRef: ...
    def append_many(self, payloads, metas) -> list[ObservationRef]: ...

    # QueryableObservationSet protocol
    def query(self) -> Query[T]: ...
    def load(self, ref: ObservationRef) -> T: ...
    def load_many(self, refs: list[ObservationRef], *, batch_size=32) -> list[T]: ...
    def iter_meta(self, *, page_size=128) -> Iterator[list[ObservationRow]]: ...
    def count(self) -> int: ...
    def capabilities(self) -> set[str]: ...

    # Introspection
    def meta(self, ref: ObservationRef) -> ObservationMeta: ...
    def info(self) -> dict[str, Any]: ...
    def stats(self) -> dict[str, Any]: ...
```

`append()` generates a UUID for `ObservationRef.id`, pickles payload into BLOB, inserts metadata row + R*Tree entry (if pose provided) + FTS entry (if text capable) + vector entry (if embedding capable).

6. **`query.py`** — Query (chainable, capability-aware)

```python
class Query(Generic[T]):
    # Hard filters
    def filter_time(self, t1: float, t2: float) -> Query[T]: ...
    def filter_before(self, t: float) -> Query[T]: ...
    def filter_after(self, t: float) -> Query[T]: ...
    def filter_near(self, pose: Pose, radius: float, *,
                    include_unlocalized: bool = False) -> Query[T]: ...
    def filter_tags(self, **tags: Any) -> Query[T]: ...
    def filter_refs(self, refs: list[ObservationRef]) -> Query[T]: ...

    # Candidate generation
    def search_text(self, text: str, *, candidate_k: int | None = None) -> Query[T]: ...
    def search_embedding(self, vector: list[float], *, candidate_k: int) -> Query[T]: ...

    # Ranking + limit
    def rank(self, **weights: float) -> Query[T]: ...
    def limit(self, k: int) -> Query[T]: ...

    # Terminals
    def fetch(self) -> list[ObservationRow]: ...
    def fetch_set(self) -> ObservationSet[T]: ...
    def count(self) -> int: ...
    def one(self) -> ObservationRow: ...
```

Query internals:
- Accumulates filter predicates, search ops, rank spec, limit
- `fetch()`: generates SQL, executes, returns rows
- `fetch_set()`: creates an ObservationSet (predicate-backed or ref-table-backed)
- search_embedding → sqlite-vec `MATCH`, writes top-k to temp table → ref-table-backed
- search_text → FTS5 `MATCH`
- filter_near → R*Tree range query
- rank → computes composite score from available score columns

7. **`observation_set.py`** — ObservationSet (lazy, re-queryable)

```python
class ObservationSet(Generic[T]):
    # Re-query
    def query(self) -> Query[T]: ...

    # Read
    def load(self, ref: ObservationRef) -> T: ...
    def load_many(self, refs, *, batch_size=32) -> list[T]: ...
    def refs(self, *, limit=None) -> list[ObservationRef]: ...
    def rows(self, *, limit=None) -> list[ObservationRow]: ...
    def one(self) -> ObservationRow: ...
    def fetch_page(self, *, limit=128, offset=0) -> list[ObservationRow]: ...
    def count(self) -> int: ...
    def capabilities(self) -> set[str]: ...
    def lineage(self) -> Lineage: ...

    # Cross-stream
    def project_to(self, stream: Stream) -> ObservationSet: ...
```

Internal backing (spec §8):

```python
@dataclass
class PredicateBacking:
    """Lazy: expressible as SQL WHERE over source stream."""
    source_name: str
    query_repr: str  # serialized query filters for replay

@dataclass
class RefTableBacking:
    """Materialized: temp table of refs + scores."""
    table_name: str  # SQLite temp table
    source_streams: list[str]
    ordered: bool = False
```

- `.query()` on predicate-backed → adds more predicates
- `.query()` on ref-table-backed → filters within that temp table
- `project_to()` → joins backing refs via lineage parent_refs to target stream

### Phase 3: Later (not in first PR)

- `derive()` with Transform protocol
- `CompositeBacking` (union/intersection/difference)
- `Correlator` / `s.correlate()`
- `retention` enforcement / cleanup
- Full introspection (stats, spatial_bounds)

## SQLite Schema (per stream)

### Metadata table: `{name}_meta`

```sql
CREATE TABLE {name}_meta (
    id TEXT PRIMARY KEY,          -- UUID, part of ObservationRef
    ts_start REAL,
    ts_end REAL,
    robot_id TEXT,
    frame_id TEXT,
    pose_x REAL, pose_y REAL, pose_z REAL,
    pose_qx REAL, pose_qy REAL, pose_qz REAL, pose_qw REAL,
    pose_source TEXT,
    pose_confidence REAL,
    payload_codec TEXT,
    payload_size_bytes INTEGER,
    tags TEXT,                     -- JSON
    parent_stream TEXT,            -- lineage: source stream name
    parent_id TEXT                 -- lineage: source observation id
);
CREATE INDEX idx_{name}_meta_ts ON {name}_meta(ts_start);
```

### Payload table: `{name}_payload`

```sql
CREATE TABLE {name}_payload (
    id TEXT PRIMARY KEY,          -- matches _meta.id
    data BLOB NOT NULL
);
```

Separate from meta so queries never touch payload BLOBs.

### R*Tree (spatial index): `{name}_rtree`

```sql
CREATE VIRTUAL TABLE {name}_rtree USING rtree(
    rowid,                        -- matches _meta rowid
    min_t, max_t,                 -- ts_start, ts_end
    min_x, max_x,
    min_y, max_y,
    min_z, max_z
);
```

Only rows with pose get R*Tree entries (spec §2.6: unlocalized != everywhere).
R*Tree `rowid` linked to meta via a mapping or using meta's rowid.

### FTS5 (text search): `{name}_fts`

```sql
CREATE VIRTUAL TABLE {name}_fts USING fts5(
    id,
    content,
    content={name}_meta,
    content_rowid=rowid
);
```

Only for streams with `"text"` capability.

### Vector index (embedding search): `{name}_vec`

```sql
CREATE VIRTUAL TABLE {name}_vec USING vec0(
    embedding float[{dim}]
);
```

`rowid` matches meta rowid. Only for streams with `"embedding"` capability.

## Key Design Decisions

### Pose type bridging

The spec defines its own lightweight `Pose(xyz, quat_xyzw)` for storage. DimOS has `dimos.msgs.geometry_msgs.Pose` with full algebra. Stream `append()` should accept either:

```python
# DimOS Pose
images.append(frame, pose=robot_pose)  # dimos.msgs.geometry_msgs.Pose

# Spec Pose (tuples)
images.append(frame, pose=Pose(xyz=(1, 2, 3), quat_xyzw=(0, 0, 0, 1)))
```

Internal conversion via `to_storage_pose()` extracts `(x, y, z, qx, qy, qz, qw)` for SQL storage.

### filter_near accepts DimOS types

```python
from dimos.msgs.geometry_msgs import Point, Pose as DimOSPose

q.filter_near(DimOSPose(1, 2, 3), radius=5.0)
q.filter_near(Point(1, 2, 3), radius=5.0)
q.filter_near(Pose(xyz=(1, 2, 3)), radius=5.0)
```

### ObservationRef identity

`id` is a UUID4 string generated on `append()`. Never reuse timestamps as identity.

### Unlocalized observations

Rows without pose are NOT inserted into R*Tree. `filter_near()` excludes them by default. `include_unlocalized=True` bypasses R*Tree and scans meta table.

### Separate payload table

Payload BLOBs live in `{name}_payload`, separate from `{name}_meta`. This ensures queries (which only touch meta + indexes) never page in multi-MB image blobs.

## Existing Code to Reuse

- `dimos/memory/timeseries/sqlite.py:29` — `_validate_identifier()` regex pattern
- `dimos/msgs/geometry_msgs/Pose.py` — DimOS Pose type, `PoseLike` type alias
- `dimos/msgs/geometry_msgs/Point.py` — Point type
- `dimos/core/resource.py` — Resource ABC (start/stop/dispose)

## Verification

1. `uv run pytest dimos/memory2/test_memory2.py -v` — all tests pass
2. `uv run mypy dimos/memory2/` — type checks clean
3. `uv run pytest dimos/memory/timeseries/test_base.py -v` — existing tests untouched

### Test scenarios (map to spec §16 acceptance examples)

- Re-query narrowed data: `filter_time → fetch_set → query → filter_near → fetch_set`
- fetch_set does not load payloads: verify no BLOB reads until explicit `load()`
- Embedding search: `search_embedding → filter_time → limit → fetch_set` → ref-table backed
- Projection: `emb_matches.project_to(images)` → fetch page → load_many
- Paginated preview: `fetch_page(limit=24, offset=0)` returns ObservationRows
- Unlocalized exclusion: rows without pose excluded from `filter_near` by default
