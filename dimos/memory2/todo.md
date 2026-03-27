# PR #1682 Review Issues

## Bugs

- [x] **test_voxel_map.py:114** — Stray `self` parameter in standalone `test_build_global_map` function (will fail at runtime)
- [x] **test_e2e.py:284** — Duplicate assertion `assert overlap_start < overlap_end` (copy-paste artifact)
- [x] **all_blueprints.py:164** — `stream-module` entry points to `StreamModule` base class; should be excluded from auto-generation like `Module`/`ModuleBase`. Add `"StreamModule"` to `_EXCLUDED_MODULE_NAMES` in `test_all_blueprints_generation.py:36`, then regenerate.

## Test Quality (paul-nechifor)

### Inline imports — move to file top
- [x] **test_module.py:217** — `import threading`
- [x] **test_module.py:219** — `from dimos.core.transport import pLCMTransport`
- [x] **test_module.py:243** — `import time` (also removed unnecessary `time.sleep(0.5)`)
- [x] **test_module.py:256** — `from dimos.utils.threadpool import get_scheduler`
- [x] **test_visualizer.py:109,165** — `MoondreamVlModel` imported twice inline
- [x] **test_visualizer.py:155** — `import pickle` inline
- [x] **test_visualizer.py:166-167** — `Detection3DPC`, `GO2Connection` inline

### Missing cleanup
- [x] **test_null.py:28,41** — `store.start()` called but never `store.stop()`. Use `with store:` context manager.
- [x] **test_module.py:253** — `module.stop()` not in try/finally; if assertion fails, cleanup is skipped

### Conditional logic in tests (should be deterministic)
- [x] **test_store.py:562** — `backend._disposables is None or backend._disposables.is_disposed` — should assert `is not None` and `is_disposed` separately
- [x] **test_store.py:575** — `if hasattr(metadata_store, "_disposables") and ...` — conditional assertion may never execute

### Print statements
- [x] **test_e2e.py** — kept; `@tool` tests where prints are useful
- [x] **test_visualizer.py** — kept; same reason

### Shared fixture pollution
- [x] **test_e2e.py:134-135** — kept; idempotency guard against persistent on-disk DB is correct

### Naming
- [x] **test_module.py:46** — `_xf` is an internal attribute; test is white-box. Low priority, skipping.

## Code Quality

- [x] **observationstore/memory.py:54** — `maxlen=max_size if max_size is not None else None` is redundant; simplify to `maxlen=max_size`
- [x] **voxels.py:55-57** — `voxel_size`, `carve_columns`, `frame_id` are public but should be private (`_`-prefixed) per paul. Updated all internal references including test_voxels.py.
- [x] **voxels.py:176-177** — `self.vbg = None  # type: ignore[assignment]` — typed field as `Optional` in `__init__` instead.
- [x] **voxels.py:106-107,174-175** — `invalidate_cache` type ignores from `@simple_mcache` — can't fix without changing decorator typing. Left as-is.

## Already Addressed / No Action

- **transform.py:116** — stride() validation for n>0 already exists (line 110)
- **test_voxels.py:110** — "injest" typo already fixed to "ingest"
- **voxels.py:216** — redundant frame_id already fixed by config model_dump approach
- **resource.py:84,87** — lazy init and return value defended by leshy
- **module.py:74,76** — subscription tracking unnecessary; store.stop() cascades to streams
- **test_voxel_map.py:32** — paul corrected himself; reading file, not writing

## Design Questions (not actionable here)

- **resource.py:84** (paul 2nd comment) — `ModuleBase` and `CompositeResource` both define `_disposables`; multiple inheritance shadowing is confusing but intentional
- **test_module.py:258** — global thread pool lifecycle is app-level; test shuts it down to pass thread-leak check. Consider a conftest fixture instead.
