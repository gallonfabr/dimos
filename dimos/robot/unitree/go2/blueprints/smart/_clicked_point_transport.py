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

"""Transport that receives PointStamped clicks from Rerun and delivers PoseStamped.

Subscribes to an LCM topic carrying PointStamped (published by the Rerun
viewer fork) and converts each message to PoseStamped via
``PointStamped.to_pose_stamped()`` before delivering to stream subscribers.

No DimOS Module is needed -- the conversion lives entirely inside the
transport layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dimos.core.transport import PubSubTransport
from dimos.msgs.geometry_msgs import PoseStamped
from dimos.msgs.geometry_msgs.PointStamped import PointStamped
from dimos.protocol.pubsub.impl.lcmpubsub import LCM, Topic as LCMTopic
from dimos.utils.logging_config import setup_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from dimos.core.stream import Out, Stream

logger = setup_logger()


class ClickedPointTransport(PubSubTransport[PoseStamped]):
    """PubSubTransport that bridges ``/clicked_point`` PointStamped -> PoseStamped.

    Internally subscribes to an LCM topic carrying ``PointStamped`` messages
    (e.g. published by the Rerun viewer) and converts each one to
    ``PoseStamped`` with identity quaternion via ``PointStamped.to_pose_stamped()``.

    Also supports local ``broadcast()`` so that other in-process producers
    (RPC ``set_goal``, agent planners) can still publish ``PoseStamped``
    directly through the same transport.

    Usage in a blueprint::

        from dimos.msgs.geometry_msgs import PoseStamped

        my_blueprint = autoconnect(...).transports({
            ("goal_request", PoseStamped): ClickedPointTransport(),
        })
    """

    _started: bool = False

    def __init__(self, clicked_point_topic: str = "/clicked_point") -> None:
        super().__init__(clicked_point_topic)
        self._click_lcm = LCM()
        self._click_topic = LCMTopic(clicked_point_topic, PointStamped)
        self._subscribers: list[Callable[[PoseStamped], Any]] = []

    # -- PubSubTransport interface -------------------------------------------

    def broadcast(self, _: Out[PoseStamped] | None, msg: PoseStamped) -> None:
        """Deliver a PoseStamped directly to all local subscribers."""
        for cb in self._subscribers:
            cb(msg)

    def subscribe(
        self,
        callback: Callable[[PoseStamped], Any],
        selfstream: Stream[PoseStamped] | None = None,
    ) -> Callable[[], None]:
        """Subscribe and also start listening for PointStamped clicks on LCM."""
        if not self._started:
            self.start()

        self._subscribers.append(callback)

        # Subscribe to the external PointStamped LCM topic; convert on receive.
        unsub_lcm = self._click_lcm.subscribe(
            self._click_topic,
            lambda msg, _topic: self._on_click(msg, callback),
        )

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
            unsub_lcm()

        return unsubscribe

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if not self._started:
            self._click_lcm.start()
            self._started = True

    def stop(self) -> None:
        if self._started:
            self._click_lcm.stop()
            self._started = False

    # -- Internal ------------------------------------------------------------

    @staticmethod
    def _on_click(
        point_stamped: PointStamped,
        callback: Callable[[PoseStamped], Any],
    ) -> None:
        pose = point_stamped.to_pose_stamped()
        logger.info(
            "ClickedPointTransport",
            point=f"({point_stamped.x:.2f}, {point_stamped.y:.2f}, {point_stamped.z:.2f})",
            pose=str(pose),
        )
        callback(pose)
