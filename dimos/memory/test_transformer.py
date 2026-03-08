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

"""Tests for memory transformers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from dimos.memory.impl.sqlite import SqliteSession, SqliteStore
from dimos.memory.transformer import TextEmbeddingTransformer, VLMDetectionTransformer
from dimos.models.embedding.base import Embedding, EmbeddingModel
from dimos.msgs.sensor_msgs.Image import Image
from dimos.perception.detection.type.detection2d.bbox import Detection2DBBox

if TYPE_CHECKING:
    from collections.abc import Iterator


class FakeTextEmbedder(EmbeddingModel):
    device = "cpu"

    def embed(self, *imgs: Image) -> Embedding | list[Embedding]:  # type: ignore[override]
        raise NotImplementedError

    def embed_text(self, *texts: str) -> Embedding | list[Embedding]:
        results = []
        for text in texts:
            h = hash(text) % 1000 / 1000.0
            results.append(Embedding(np.array([h, 1.0 - h, 0.0, 0.0], dtype=np.float32)))
        return results if len(results) > 1 else results[0]


class SemanticFakeEmbedder(EmbeddingModel):
    """Embeds 'kitchen' texts to one region, everything else to another."""

    device = "cpu"

    def embed(self, *imgs: Image) -> Embedding | list[Embedding]:  # type: ignore[override]
        raise NotImplementedError

    def embed_text(self, *texts: str) -> Embedding | list[Embedding]:
        results = []
        for text in texts:
            if "kitchen" in text.lower():
                results.append(Embedding(np.array([1.0, 0.0, 0.0], dtype=np.float32)))
            else:
                results.append(Embedding(np.array([0.0, 1.0, 0.0], dtype=np.float32)))
        return results if len(results) > 1 else results[0]


@pytest.fixture
def session(tmp_path: object) -> Iterator[SqliteSession]:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    store = SqliteStore(str(tmp_path / "test.db"))
    sess = store.session()
    yield sess
    sess.stop()
    store.stop()


class TestTextEmbeddingTransformer:
    """Test text -> embedding -> semantic search pipeline."""

    def test_text_to_embedding_backfill(self, session: SqliteSession) -> None:
        """Backfill: store text, transform to embeddings, search by text."""
        logs = session.stream("te_logs", str)
        logs.append("Robot navigated to kitchen", ts=1.0)
        logs.append("Battery low warning", ts=2.0)
        logs.append("Robot navigated to bedroom", ts=3.0)

        emb_stream = logs.transform(TextEmbeddingTransformer(FakeTextEmbedder())).store(
            "te_log_embeddings"
        )

        assert emb_stream.count() == 3

        results = emb_stream.search_embedding("Robot navigated to kitchen", k=1).fetch()
        assert len(results) == 1
        assert isinstance(results[0].data, Embedding)

        # project_to to get source text
        projected = (
            emb_stream.search_embedding("Robot navigated to kitchen", k=1).project_to(logs).fetch()
        )
        assert len(projected) == 1
        assert isinstance(projected[0].data, str)

    def test_text_embedding_live(self, session: SqliteSession) -> None:
        """Live mode: new text is embedded automatically."""
        logs = session.stream("te_live_logs", str)
        emb_stream = logs.transform(TextEmbeddingTransformer(FakeTextEmbedder()), live=True).store(
            "te_live_embs"
        )

        assert emb_stream.count() == 0  # no backfill

        logs.append("New log entry", ts=1.0)
        assert emb_stream.count() == 1

        logs.append("Another log entry", ts=2.0)
        assert emb_stream.count() == 2

    def test_text_embedding_search_and_project(self, session: SqliteSession) -> None:
        """search_embedding + project_to retrieves source text."""
        logs = session.stream("te_proj_logs", str)
        logs.append("Robot entered kitchen", ts=1.0)
        logs.append("Battery warning", ts=2.0)
        logs.append("Cleaning kitchen floor", ts=3.0)

        emb_stream = logs.transform(TextEmbeddingTransformer(SemanticFakeEmbedder())).store(
            "te_proj_embs"
        )

        results = emb_stream.search_embedding("kitchen", k=2).project_to(logs).fetch()
        assert len(results) == 2
        assert all("kitchen" in r.data.lower() for r in results)


# ── Fake VLM for detection tests ─────────────────────────────────────


def _make_image(width: int = 640, height: int = 480) -> Image:
    """Create a simple test image."""
    return Image(np.zeros((height, width, 3), dtype=np.uint8))


class _FakeImageDetections2D:
    """Mimics ImageDetections2D with a .detections list."""

    def __init__(self, detections: list[Detection2DBBox]) -> None:
        self.detections = detections


class FakeVlModel:
    """Fake VlModel that returns canned detections per call.

    Pass a list of detection lists — one per call to query_detections().
    Each call pops the next entry from the list.
    """

    def __init__(
        self, detections_per_call: list[list[tuple[str, float, float, float, float]]]
    ) -> None:
        self._queue = list(detections_per_call)

    def query_detections(self, image: Image, query: str) -> _FakeImageDetections2D:
        raw = self._queue.pop(0) if self._queue else []
        ts = image.ts
        dets = []
        for i, (name, x1, y1, x2, y2) in enumerate(raw):
            dets.append(
                Detection2DBBox(
                    bbox=(x1, y1, x2, y2),
                    track_id=i,
                    class_id=-1,
                    confidence=0.9,
                    name=name,
                    ts=ts,
                    image=image,
                )
            )
        return _FakeImageDetections2D(dets)


class TestVLMDetectionTransformer:
    """Test VLM detection transformer."""

    def test_vlm_detection_backfill(self, session: SqliteSession) -> None:
        """3 images, VLM finds 1 detection per image → 3 detections with parent_id."""
        frames = session.stream("vlm_frames", Image)
        frames.append(_make_image(), ts=1.0)
        frames.append(_make_image(), ts=2.0)
        frames.append(_make_image(), ts=3.0)

        vlm = FakeVlModel(
            [
                [("bottle", 10, 20, 100, 200)],
                [("bottle", 50, 60, 150, 250)],
                [("bottle", 30, 40, 130, 230)],
            ]
        )

        det_stream = frames.transform(
            VLMDetectionTransformer(vlm, query="bottle")  # type: ignore[arg-type]
        ).store("vlm_detections", Detection2DBBox)

        results = det_stream.fetch()
        assert len(results) == 3

        # All detections have parent_id linking back to source frames
        frame_ids = {obs.id for obs in frames.fetch()}
        for det_obs in results:
            assert det_obs.parent_id in frame_ids
            assert det_obs.data.image is None  # stored without image
            assert det_obs.data.name == "bottle"
            assert det_obs.tags["query"] == "bottle"

    def test_vlm_detection_no_matches(self, session: SqliteSession) -> None:
        """VLM returns empty detections → stream stays empty."""
        frames = session.stream("vlm_empty_frames", Image)
        frames.append(_make_image(), ts=1.0)
        frames.append(_make_image(), ts=2.0)

        vlm = FakeVlModel([[], []])  # no detections for either call

        det_stream = frames.transform(
            VLMDetectionTransformer(vlm, query="cat")  # type: ignore[arg-type]
        ).store("vlm_empty_dets", Detection2DBBox)

        assert det_stream.count() == 0

    def test_vlm_detection_multiple_per_frame(self, session: SqliteSession) -> None:
        """1 image → 3 detections, all share same parent_id."""
        frames = session.stream("vlm_multi_frames", Image)
        frames.append(_make_image(), ts=1.0)

        vlm = FakeVlModel(
            [
                [
                    ("bottle", 10, 20, 100, 200),
                    ("cup", 200, 100, 300, 250),
                    ("plate", 400, 300, 500, 400),
                ],
            ]
        )

        det_stream = frames.transform(
            VLMDetectionTransformer(vlm, query="objects")  # type: ignore[arg-type]
        ).store("vlm_multi_dets", Detection2DBBox)

        results = det_stream.fetch()
        assert len(results) == 3

        # All share the same parent_id (the single source frame)
        parent_ids = {obs.parent_id for obs in results}
        assert len(parent_ids) == 1

        names = {obs.data.name for obs in results}
        assert names == {"bottle", "cup", "plate"}

        parent_ids = {obs.parent_id for obs in results}
        assert len(parent_ids) == 1

        names = {obs.data.name for obs in results}
        assert names == {"bottle", "cup", "plate"}
