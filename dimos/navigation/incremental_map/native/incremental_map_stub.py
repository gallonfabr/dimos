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

"""Stub native executable for IncrementalMap.

This Python script acts as a placeholder for the future C++/Rust implementation.
It implements the same CLI interface that the NativeModule wrapper expects:

  --odom <topic>              LCM topic for incoming Odometry
  --registered_scan <topic>   LCM topic for incoming PointCloud2
  --global_map <topic>        LCM topic to publish PointCloud2 global map
  --corrected_odom <topic>    LCM topic to publish corrected Odometry
  --voxel_size <float>        Voxel grid resolution (default: 0.15)
  --key_trans <float>         Keyframe translation threshold (default: 0.5)
  --key_deg <float>           Keyframe rotation threshold (default: 10.0)
  --loop_search_radius <float> Loop closure search radius (default: 3.0)
  --loop_time_thresh <float>   Time gap for loop candidates (default: 10.0)
  --loop_score_thresh <float>  ICP fitness threshold (default: 0.5)
  --map_publish_rate <float>   Map publish rate in Hz (default: 0.5)

The C++ port should:
  1. Parse these same CLI args with getopt/CLI11/args
  2. Subscribe to odom and registered_scan via LCM
  3. Maintain the same _IncrementalMapCore algorithm in C++
  4. Publish global_map and corrected_odom via LCM
  5. Use the same voxel-hash + KD-tree + ICP logic
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

# Guard: only import lcm if available (allows dry-run testing of CLI interface)
try:
    import lcm  # type: ignore[import-not-found]

    _LCM_AVAILABLE = True
except ImportError:
    lcm = None  # type: ignore[assignment]
    _LCM_AVAILABLE = False


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments as the native process expects them."""
    p = argparse.ArgumentParser(
        description="Incremental Map native stub (placeholder for C++/Rust port)"
    )
    # LCM topic names (injected by NativeModule._collect_topics)
    p.add_argument("--odom", default="/odom")
    p.add_argument("--registered_scan", default="/registered_scan")
    p.add_argument("--global_map", default="/global_map")
    p.add_argument("--corrected_odom", default="/corrected_odom")
    # Config parameters (from NativeModuleConfig.to_cli_args)
    p.add_argument("--voxel_size", type=float, default=0.15)
    p.add_argument("--key_trans", type=float, default=0.5)
    p.add_argument("--key_deg", type=float, default=10.0)
    p.add_argument("--loop_search_radius", type=float, default=3.0)
    p.add_argument("--loop_time_thresh", type=float, default=10.0)
    p.add_argument("--loop_score_thresh", type=float, default=0.5)
    p.add_argument("--loop_submap_half_range", type=int, default=3)
    p.add_argument("--icp_max_iter", type=int, default=30)
    p.add_argument("--icp_max_dist", type=float, default=5.0)
    p.add_argument("--min_loop_detect_duration", type=float, default=5.0)
    p.add_argument("--map_publish_rate", type=float, default=0.5)
    p.add_argument("--registered_input", default="true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(
        f"[IncrementalMapStub] Starting — "
        f"odom={args.odom} scan={args.registered_scan} "
        f"map={args.global_map} voxel={args.voxel_size}",
        flush=True,
    )

    if not _LCM_AVAILABLE:
        print(
            "[IncrementalMapStub] WARNING: lcm not available — running in dry-run mode",
            file=sys.stderr,
            flush=True,
        )
        # In dry-run mode, just sleep until terminated (for testing CLI parsing)
        import threading as _threading

        stop_event = _threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())
        stop_event.wait()
        print("[IncrementalMapStub] Terminated (dry-run)", flush=True)
        return

    # ── Real LCM mode ──
    import numpy as np
    from scipy.spatial.transform import Rotation

    from dimos.msgs.nav_msgs.Odometry import Odometry
    from dimos.msgs.sensor_msgs.PointCloud2 import PointCloud2
    from dimos.navigation.incremental_map.module import IncrementalMapConfig, _IncrementalMapCore

    cfg = IncrementalMapConfig(
        voxel_size=args.voxel_size,
        key_trans=args.key_trans,
        key_deg=args.key_deg,
        loop_search_radius=args.loop_search_radius,
        loop_time_thresh=args.loop_time_thresh,
        loop_score_thresh=args.loop_score_thresh,
        loop_submap_half_range=args.loop_submap_half_range,
        icp_max_iter=args.icp_max_iter,
        icp_max_dist=args.icp_max_dist,
        min_loop_detect_duration=args.min_loop_detect_duration,
        map_publish_rate=args.map_publish_rate,
        registered_input=args.registered_input.lower() in ("true", "1"),
    )
    core = _IncrementalMapCore(cfg)
    lc = lcm.LCM()
    import threading

    lock = threading.Lock()
    last_r = np.eye(3)
    last_t = np.zeros(3)
    last_ts = 0.0
    has_odom = False

    def on_odom(channel: str, data: bytes) -> None:  # type: ignore[misc]
        nonlocal last_r, last_t, last_ts, has_odom
        msg = Odometry.decode(data)  # type: ignore[attr-defined]
        q = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
        r = Rotation.from_quat(q).as_matrix()
        t = np.array([msg.x, msg.y, msg.z])
        with lock:
            last_r, last_t, last_ts = r, t, msg.ts or time.time()
            has_odom = True

    def on_scan(channel: str, data: bytes) -> None:  # type: ignore[misc]
        msg = PointCloud2.decode(data)  # type: ignore[attr-defined]
        pts, _ = msg.as_numpy()
        if len(pts) == 0:
            return
        with lock:
            if not has_odom:
                return
            r, t, ts = last_r.copy(), last_t.copy(), last_ts

        registered = cfg.registered_input
        body_pts = (r.T @ (pts[:, :3].T - t[:, None])).T if registered else pts[:, :3].copy()

        with lock:
            added = core.add_scan(r, t, body_pts, ts)
            if added:
                core.detect_and_correct_loop()
                r_c, t_c = core.get_corrected_pose(r, t)
                from dimos.msgs.geometry_msgs.Pose import Pose

                q_c = Rotation.from_matrix(r_c).as_quat()
                odom_out = Odometry(
                    ts=ts,
                    frame_id="map",
                    child_frame_id="sensor",
                    pose=Pose(position=list(t_c), orientation=list(q_c)),
                )
                lc.publish(args.corrected_odom, odom_out.encode())  # type: ignore[attr-defined]

    lc.subscribe(args.odom, on_odom)
    lc.subscribe(args.registered_scan, on_scan)

    # Map publish thread
    stop_event = threading.Event()

    def map_loop() -> None:
        interval = 1.0 / cfg.map_publish_rate if cfg.map_publish_rate > 0 else 2.0
        last_pub = 0.0
        while not stop_event.is_set():
            now = time.time()
            if now - last_pub > interval:
                with lock:
                    n_kf = core.num_keyframes
                if n_kf > 0:
                    with lock:
                        cloud = core.build_global_map()
                    if len(cloud) > 0:
                        pc = PointCloud2.from_numpy(cloud, frame_id="map", timestamp=now)
                        lc.publish(args.global_map, pc.encode())  # type: ignore[attr-defined]
                last_pub = now
            time.sleep(0.05)

    map_thread = threading.Thread(target=map_loop, daemon=True)
    map_thread.start()

    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())

    print("[IncrementalMapStub] Running (LCM mode)", flush=True)
    while not stop_event.is_set():
        lc.handle_timeout(100)

    print("[IncrementalMapStub] Terminated", flush=True)


if __name__ == "__main__":
    main()
