# G1 Low-Level Control

Direct 29-DOF joint control for the Unitree G1 humanoid over DDS at 500 Hz.

## Prerequisites

- Unitree G1 reachable at `192.168.123.164`
- Network interface connected to the robot (e.g. `enp60s0`)
- CycloneDDS configured: `export CYCLONEDDS_HOME=/home/mustafa/cyclonedds/install`

## Blueprints

### `unitree-g1-lowlevel` — Coordinator Only

Starts the ControlCoordinator with the G1 whole-body adapter. Publishes joint state on LCM and accepts joint commands. No built-in control logic — use with the record script or your own controller.

```bash
ROBOT_INTERFACE=enp60s0 dimos run unitree-g1-lowlevel
```

LCM topics:
- `/coordinator/joint_state` — 500 Hz `JointState` with 29 joint positions, velocities, efforts
- `/g1/joint_command` — accepts `JointState` position commands

### `unitree-g1-playback` — Trajectory Playback

Replays a previously recorded JSON trajectory file through the coordinator.

```bash
TRAJECTORY_FILE=macarena.json ROBOT_INTERFACE=enp60s0 dimos run unitree-g1-playback
```

## Examples

### Record a Trajectory

While `unitree-g1-lowlevel` is running in another terminal, record all joint states to a JSON file:

```bash
# Terminal 1: start the coordinator
ROBOT_INTERFACE=enp60s0 dimos run unitree-g1-lowlevel

# Terminal 2: record joint states
RECORD_FILE=macarena.json python -m dimos.control.examples.g1_record
```

Manually move the robot's joints while recording. Press Ctrl+C to stop and save.

Output format:
```json
{
  "joint_names": ["g1_LeftHipPitch", "g1_LeftHipRoll", "..."],
  "samples": [
    {"ts": 1709712345.123, "position": [0.0, 0.1, "..."]},
    {"ts": 1709712345.125, "position": [0.0, 0.1, "..."]}
  ]
}
```

### Play Back a Trajectory

```bash
TRAJECTORY_FILE=macarena.json ROBOT_INTERFACE=enp60s0 dimos run unitree-g1-playback
```

The playback module:
1. Waits for the first joint state from the coordinator
2. Interpolates from the current position to the first recorded sample over 1 second
3. Replays the trajectory at original timing (using timestamp deltas)
4. Loops indefinitely until stopped

### Zero Posture + Oscillation (SDK Example)

A standalone control module that replicates the Unitree SDK `g1_low_level_example.py`:

1. Interpolates all joints to zero posture (3s)
2. Oscillates ankle pitch/roll (3s)
3. Oscillates ankles + wrist roll (indefinitely)

This module (`g1_zero_posture.py`) is not wired into any blueprint by default. To use it, create a blueprint that composes it with the coordinator.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROBOT_INTERFACE` | `enp86s0` | Network interface for DDS communication |
| `RECORD_FILE` | `g1_recording.json` | Output path for the record script |
| `TRAJECTORY_FILE` | *(required)* | JSON trajectory file for playback |

## Joint Map (29 DOF)

| Index | Joint | Index | Joint |
|-------|-------|-------|-------|
| 0 | LeftHipPitch | 15 | LeftShoulderPitch |
| 1 | LeftHipRoll | 16 | LeftShoulderRoll |
| 2 | LeftHipYaw | 17 | LeftShoulderYaw |
| 3 | LeftKnee | 18 | LeftElbow |
| 4 | LeftAnklePitch | 19 | LeftWristRoll |
| 5 | LeftAnkleRoll | 20 | LeftWristPitch |
| 6 | RightHipPitch | 21 | LeftWristYaw |
| 7 | RightHipRoll | 22 | RightShoulderPitch |
| 8 | RightHipYaw | 23 | RightShoulderRoll |
| 9 | RightKnee | 24 | RightShoulderYaw |
| 10 | RightAnklePitch | 25 | RightElbow |
| 11 | RightAnkleRoll | 26 | RightWristRoll |
| 12 | WaistYaw | 27 | RightWristPitch |
| 13 | WaistRoll | 28 | RightWristYaw |
| 14 | WaistPitch | | |

Joint names in LCM messages are prefixed with the hardware ID: `g1_LeftHipPitch`, `g1_RightWristYaw`, etc.
