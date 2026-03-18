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

"""Single-arm coordinator blueprints with trajectory control.

Usage:
    dimos run coordinator-mock           # Mock 7-DOF arm
    dimos run coordinator-xarm7          # XArm7 real hardware
    dimos run coordinator-xarm6          # XArm6 real hardware
    dimos run coordinator-piper          # Piper arm (CAN bus)
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

# Minimal blueprint (no hardware, no tasks)
coordinator_basic = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# Mock 7-DOF arm (for testing)
coordinator_mock = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("arm", 7),
            adapter_type="mock",
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_arm",
            type="trajectory",
            joint_names=[f"arm_joint{i + 1}" for i in range(7)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# XArm7 real hardware
coordinator_xarm7 = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("arm", 7),
            adapter_type="xarm",
            address=_XARM7_IP,
            auto_enable=True,
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_arm",
            type="trajectory",
            joint_names=[f"arm_joint{i + 1}" for i in range(7)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# XArm6 real hardware
coordinator_xarm6 = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("arm", 6),
            adapter_type="xarm",
            address=_XARM6_IP,
            auto_enable=True,
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_xarm",
            type="trajectory",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)

# Piper arm (6-DOF, CAN bus)
coordinator_piper = control_coordinator(
    tick_rate=100.0,
    publish_joint_state=True,
    joint_state_frame_id="coordinator",
    hardware=[
        HardwareComponent(
            hardware_id="arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("arm", 6),
            adapter_type="piper",
            address=_CAN_PORT,
            auto_enable=True,
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_piper",
            type="trajectory",
            joint_names=[f"arm_joint{i + 1}" for i in range(6)],
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
    }
)


__all__ = [
    "coordinator_basic",
    "coordinator_mock",
    "coordinator_xarm7",
    "coordinator_xarm6",
    "coordinator_piper",
]
