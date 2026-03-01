#!/usr/bin/env python3
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

"""Tests for ClickedPointTransport.

Verifies that PointStamped messages published on /clicked_point LCM
are received as PoseStamped with correct coordinates and identity quaternion.
"""

import threading
import time

import pytest

from dimos.msgs.geometry_msgs.PointStamped import PointStamped
from dimos.msgs.geometry_msgs.PoseStamped import PoseStamped
from dimos.protocol.pubsub.impl.lcmpubsub import LCM, Topic as LCMTopic
from dimos.robot.unitree.go2.blueprints.smart._clicked_point_transport import (
    ClickedPointTransport,
)


@pytest.fixture()
def transport():
    """Create and start a ClickedPointTransport, stop after test."""
    t = ClickedPointTransport("/test_clicked_point")
    yield t
    t.stop()


@pytest.fixture()
def publisher():
    """An LCM publisher for PointStamped on the test topic."""
    lcm = LCM()
    lcm.start()
    yield lcm
    lcm.stop()


class TestClickedPointTransport:
    """Unit tests for the converting transport."""

    def test_receives_point_as_pose(self, transport: ClickedPointTransport, publisher: LCM):
        """PointStamped on LCM → subscriber receives PoseStamped."""
        received: list[PoseStamped] = []
        event = threading.Event()

        def on_msg(pose: PoseStamped) -> None:
            received.append(pose)
            event.set()

        transport.subscribe(on_msg)

        # Publish a PointStamped via LCM.
        point = PointStamped(x=1.5, y=2.5, z=0.0, frame_id="map")
        topic = LCMTopic("/test_clicked_point", PointStamped)
        publisher.publish(topic, point)

        assert event.wait(timeout=5.0), "Timed out waiting for converted message"
        assert len(received) == 1

        pose = received[0]
        assert isinstance(pose, PoseStamped)
        assert pose.x == pytest.approx(1.5)
        assert pose.y == pytest.approx(2.5)
        assert pose.z == pytest.approx(0.0)
        # Identity quaternion (x, y, z, w) = (0, 0, 0, 1)
        assert pose.orientation.x == pytest.approx(0.0)
        assert pose.orientation.y == pytest.approx(0.0)
        assert pose.orientation.z == pytest.approx(0.0)
        assert pose.orientation.w == pytest.approx(1.0)
        assert pose.frame_id == "map"

    def test_broadcast_delivers_pose_directly(self, transport: ClickedPointTransport):
        """broadcast() delivers PoseStamped to subscribers without LCM."""
        received: list[PoseStamped] = []
        transport.subscribe(lambda pose: received.append(pose))

        pose = PoseStamped(
            position=[3.0, 4.0, 0.0],
            orientation=[0.0, 0.0, 0.0, 1.0],
            frame_id="map",
        )
        transport.broadcast(None, pose)

        assert len(received) == 1
        assert received[0].x == pytest.approx(3.0)
        assert received[0].y == pytest.approx(4.0)

    def test_unsubscribe_stops_delivery(self, transport: ClickedPointTransport, publisher: LCM):
        """After unsubscribe, no more messages are delivered."""
        received: list[PoseStamped] = []
        unsub = transport.subscribe(lambda pose: received.append(pose))

        # Unsubscribe immediately.
        unsub()

        # Publish — should NOT be received.
        point = PointStamped(x=9.0, y=9.0, z=0.0, frame_id="map")
        topic = LCMTopic("/test_clicked_point", PointStamped)
        publisher.publish(topic, point)
        time.sleep(0.5)

        assert len(received) == 0

    def test_multiple_clicks(self, transport: ClickedPointTransport, publisher: LCM):
        """Multiple clicks each produce a PoseStamped."""
        received: list[PoseStamped] = []
        event = threading.Event()

        def on_msg(pose: PoseStamped) -> None:
            received.append(pose)
            if len(received) >= 3:
                event.set()

        transport.subscribe(on_msg)

        topic = LCMTopic("/test_clicked_point", PointStamped)
        for i in range(3):
            point = PointStamped(x=float(i), y=float(i * 2), z=0.0, frame_id="map")
            publisher.publish(topic, point)
            time.sleep(0.05)  # small gap between publishes

        assert event.wait(timeout=5.0), "Timed out waiting for 3 messages"
        assert len(received) == 3
        assert received[0].x == pytest.approx(0.0)
        assert received[1].x == pytest.approx(1.0)
        assert received[2].x == pytest.approx(2.0)
