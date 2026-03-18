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

"""Mobile manipulation coordinator blueprints.

Usage:
    dimos run coordinator-mock-twist-base      # Mock holonomic base
    dimos run coordinator-mobile-manip-mock    # Mock arm + base
"""

from __future__ import annotations

from dimos.control.components import HardwareComponent, HardwareType, make_joints, make_twist_base_joints
from dimos.control.coordinator import TaskConfig, control_coordinator
from dimos.core.transport import LCMTransport
from dimos.msgs.geometry_msgs.Twist import Twist
from dimos.msgs.sensor_msgs.JointState import JointState

# Mock holonomic twist base (3-DOF: vx, vy, wz)
_base_joints = make_twist_base_joints("base")
coordinator_mock_twist_base = control_coordinator(
    hardware=[
        HardwareComponent(
            hardware_id="base",
            hardware_type=HardwareType.BASE,
            joints=_base_joints,
            adapter_type="mock_twist_base",
        ),
    ],
    tasks=[
        TaskConfig(
            name="vel_base",
            type="velocity",
            joint_names=_base_joints,
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("twist_command", Twist): LCMTransport("/cmd_vel", Twist),
    }
)


# Mock arm (7-DOF) + mock holonomic base (3-DOF)
_mm_base_joints = make_twist_base_joints("base")
coordinator_mobile_manip_mock = control_coordinator(
    hardware=[
        HardwareComponent(
            hardware_id="arm",
            hardware_type=HardwareType.MANIPULATOR,
            joints=make_joints("arm", 7),
            adapter_type="mock",
        ),
        HardwareComponent(
            hardware_id="base",
            hardware_type=HardwareType.BASE,
            joints=_mm_base_joints,
            adapter_type="mock_twist_base",
        ),
    ],
    tasks=[
        TaskConfig(
            name="traj_arm",
            type="trajectory",
            joint_names=[f"arm_joint{i + 1}" for i in range(7)],
            priority=10,
        ),
        TaskConfig(
            name="vel_base",
            type="velocity",
            joint_names=_mm_base_joints,
            priority=10,
        ),
    ],
).transports(
    {
        ("joint_state", JointState): LCMTransport("/coordinator/joint_state", JointState),
        ("twist_command", Twist): LCMTransport("/cmd_vel", Twist),
    }
)


__all__ = [
    "coordinator_mock_twist_base",
    "coordinator_mobile_manip_mock",
]
