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

"""Dual-arm coordinator blueprints with trajectory control.

Usage:
    dimos run coordinator-dual-mock      # Mock 7+6 DOF arms
    dimos run coordinator-dual-xarm      # XArm7 left + XArm6 right
    dimos run coordinator-piper-xarm     # XArm6 + Piper
"""

from __future__ import annotations

import os

from dimos.control.components import HardwareComponent, HardwareType, make_joints
from dimos.control.coordinator import TaskConfig, control_coordinator
from dimos.core.transport import LCMTransport
from dimos.msgs.sensor_msgs.JointState import JointState

_XARM7_IP = os.getenv("XARM7_IP")
_XARM6_IP = os.getenv("XARM6_IP")
_CAN_PORT = os.getenv("CAN_PORT", "can0")

# Dual mock arms (7-DOF left, 6-DOF right)
coordinator_dual_mock = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="left_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("left_arm", 7),
            adapter_type="mock",
        ),
        HardwareComponent(
            hardware_id="right_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("right_arm", 6),
            adapter_type="mock",
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_left",
            type="trajectory",
            joint_names=[f"left_arm_joint{i + 1}" for i in range(7)],
            priority=10,
        ),
        TaskConfig(
            name="traj_right",
            type="trajectory",
            joint_names=[f"right_arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# Dual XArm (XArm7 left, XArm6 right)
coordinator_dual_xarm = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="left_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("left_arm", 7),
            adapter_type="xarm",
            address=_XARM7_IP,
            auto_enable=True,
        ),
        HardwareComponent(
            hardware_id="right_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("right_arm", 6),
            adapter_type="xarm",
            address=_XARM6_IP,
            auto_enable=True,
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_left",
            type="trajectory",
            joint_names=[f"left_arm_joint{i + 1}" for i in range(7)],
            priority=10,
        ),
        TaskConfig(
            name="traj_right",
            type="trajectory",
            joint_names=[f"right_arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# Dual arm (XArm6 + Piper)
coordinator_piper_xarm = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="xarm_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("xarm_arm", 6),
            adapter_type="xarm",
            address=_XARM6_IP,
            auto_enable=True,
        ),
        HardwareComponent(
            hardware_id="piper_arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("piper_arm", 6),
            adapter_type="piper",
            address=_CAN_PORT,
            auto_enable=True,
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_xarm",
            type="trajectory",
            joint_names=[f"xarm_arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
        TaskConfig(
            name="traj_piper",
            type="trajectory",
            joint_names=[f"piper_arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)


__all__ = [
    "coordinator_dual_mock",
    "coordinator_dual_xarm",
    "coordinator_piper_xarm",
]
