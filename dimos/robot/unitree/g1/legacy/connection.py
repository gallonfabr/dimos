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

"""Backward-compatible G1 connection module.

Prefer the dedicated high-level modules under
:mod:`dimos.robot.unitree.g1.effectors.high_level` for new code:

* :class:`G1HighLevelWebRtc` -- WebRTC transport
* :class:`G1HighLevelDdsSdk`    -- native Unitree SDK2 / DDS transport
"""

from typing import Any

from reactivex.disposable import Disposable

from dimos.core import In, Module, rpc
from dimos.core.global_config import GlobalConfig, global_config
from dimos.msgs.geometry_msgs import Twist
from dimos.robot.unitree.connection import UnitreeWebRTCConnection

# Re-export the new high-level modules for discoverability.
from dimos.robot.unitree.g1.effectors.high_level.dds_sdk import G1HighLevelDdsSdk
from dimos.robot.unitree.g1.effectors.high_level.spec import HighLevelG1Spec
from dimos.robot.unitree.g1.effectors.high_level.webrtc import G1HighLevelWebRtc
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


class G1Connection(Module):
    """Backward-compatible G1 connection that dispatches to WebRTC or SDK.

    New code should use :class:`G1HighLevelWebRtc` or
    :class:`G1HighLevelDdsSdk` directly.
    """

    cmd_vel: In[Twist]
    ip: str | None
    connection_type: str | None = None
    network_interface: str = "eth0"
    _global_config: GlobalConfig

    connection: UnitreeWebRTCConnection | Any | None  # Any for onboard connection

    def __init__(
        self,
        ip: str | None = None,
        connection_type: str | None = None,
        network_interface: str = "eth0",
        cfg: GlobalConfig = global_config,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._global_config = cfg
        self.ip = ip if ip is not None else self._global_config.robot_ip
        self.connection_type = connection_type or self._global_config.unitree_connection_type
        self.network_interface = network_interface
        self.connection = None
        super().__init__(*args, **kwargs)

    @rpc
    def start(self) -> None:
        super().start()

        match self.connection_type:
            case "webrtc":
                assert self.ip is not None, "IP address must be provided"
                self.connection = UnitreeWebRTCConnection(self.ip)
            case "onboard":
                # Use native SDK for onboard control
                from dimos.robot.unitree.g1.onboard_connection import G1OnboardConnection

                mode = getattr(self._global_config, "g1_mode", "ai")
                logger.info(f"Using onboard SDK connection on {self.network_interface}")
                self.connection = G1OnboardConnection(
                    network_interface=self.network_interface, mode=mode
                )
            case "replay":
                raise ValueError("Replay connection not implemented for G1 robot")
            case "mujoco":
                raise ValueError(
                    "This module does not support simulation, use G1SimConnection instead"
                )
            case _:
                raise ValueError(f"Unknown connection type: {self.connection_type}")

        assert self.connection is not None
        self.connection.start()

        self._disposables.add(Disposable(self.cmd_vel.subscribe(self.move)))

    @rpc
    def stop(self) -> None:
        assert self.connection is not None
        self.connection.stop()
        super().stop()

    @rpc
    def move(self, twist: Twist, duration: float = 0.0) -> None:
        assert self.connection is not None
        self.connection.move(twist, duration)

    @rpc
    def publish_request(self, topic: str, data: dict[str, Any]) -> dict[Any, Any]:
        logger.info(f"Publishing request to topic: {topic} with data: {data}")
        assert self.connection is not None
        return self.connection.publish_request(topic, data)  # type: ignore[no-any-return]


g1_connection = G1Connection.blueprint

__all__ = [
    "G1Connection",
    "G1HighLevelDdsSdk",
    "G1HighLevelWebRtc",
    "HighLevelG1Spec",
    "g1_connection",
]
