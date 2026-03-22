#!/usr/bin/env python3
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

"""Go2 IncrementalNav: IncrementalMap + VoxelMapper + CostMapper + Planner.

Like ``unitree_go2_smartnav`` but replaces PGO + ScanCorrector with the
lighter-weight IncrementalMap module (no GTSAM dependency).

Data flow:
    GO2Connection.lidar  (remapped → registered_scan) → IncrementalMap
    GO2Connection.odom   (remapped → raw_odom)         → IncrementalMap.odom
    IncrementalMap.global_map                           → VoxelGridMapper
    IncrementalMap.corrected_odom                       → (downstream via odom)
    VoxelGridMapper → CostMapper → ReplanningAStarPlanner
    ReplanningAStarPlanner.cmd_vel → GO2Connection

Usage:
    dimos run unitree-go2-incremental-nav --robot-ip 192.168.123.161
"""

from dimos.core.blueprints import autoconnect
from dimos.mapping.costmapper import CostMapper
from dimos.mapping.voxels import VoxelGridMapper
from dimos.navigation.frontier_exploration.wavefront_frontier_goal_selector import (
    WavefrontFrontierExplorer,
)
from dimos.navigation.incremental_map.module import IncrementalMap
from dimos.navigation.replanning_a_star.module import ReplanningAStarPlanner
from dimos.robot.unitree.go2.blueprints.basic.unitree_go2_basic import unitree_go2_basic
from dimos.robot.unitree.go2.connection import GO2Connection

unitree_go2_incremental_nav = (
    autoconnect(
        unitree_go2_basic,
        GO2Connection.blueprint(publish_tf=False),
        IncrementalMap.blueprint(),
        VoxelGridMapper.blueprint(voxel_size=0.1),
        CostMapper.blueprint(),
        ReplanningAStarPlanner.blueprint(),
        WavefrontFrontierExplorer.blueprint(),
    )
    .global_config(n_workers=8, robot_model="unitree_go2")
    .remappings(
        [
            (GO2Connection, "lidar", "registered_scan"),
            (GO2Connection, "odom", "raw_odom"),
            (VoxelGridMapper, "lidar", "global_map"),
        ]
    )
)

__all__ = ["unitree_go2_incremental_nav"]
