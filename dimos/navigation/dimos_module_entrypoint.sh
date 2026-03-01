#!/bin/bash
echo '
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ros2_ws/install/setup.bash
source /opt/dimos-venv/bin/activate
rosspy
' > /usr/bin/ross
chmod +x /usr/bin/ross

source /opt/dimos-venv/bin/activate

# Minimal CMU Unity simulation entrypoint.
# Purpose: bring up Unity + ROS nav stack and keep retrying until Unity sensor
# topics are actually registered in ROS.

# Intentionally no `set -e`: transient bridge failures are expected and retried.

STACK_ROOT="/ros2_ws/src/ros-navigation-autonomy-stack"
UNITY_EXECUTABLE="${STACK_ROOT}/src/base_autonomy/vehicle_simulator/mesh/unity/environment/Model.x86_64"
UNITY_MESH_DIR="${STACK_ROOT}/src/base_autonomy/vehicle_simulator/mesh/unity"

MODE="${MODE:-unity_sim}"
USE_ROUTE_PLANNER="${USE_ROUTE_PLANNER:-true}"
LOCALIZATION_METHOD="${LOCALIZATION_METHOD:-arise_slam}"

UNITY_BRIDGE_CONNECT_TIMEOUT_SEC="${UNITY_BRIDGE_CONNECT_TIMEOUT_SEC:-25}"
UNITY_BRIDGE_RETRY_INTERVAL_SEC="${UNITY_BRIDGE_RETRY_INTERVAL_SEC:-2}"

ROS_NAV_PID=""
UNITY_PID=""

cleanup() {
    if [ -n "$ROS_NAV_PID" ] && kill -0 "$ROS_NAV_PID" 2>/dev/null; then
        kill -TERM "-$ROS_NAV_PID" 2>/dev/null || kill -TERM "$ROS_NAV_PID" 2>/dev/null || true
        sleep 1
        kill -KILL "-$ROS_NAV_PID" 2>/dev/null || kill -KILL "$ROS_NAV_PID" 2>/dev/null || true
    fi

    if [ -n "$UNITY_PID" ] && kill -0 "$UNITY_PID" 2>/dev/null; then
        kill -TERM "$UNITY_PID" 2>/dev/null || true
        sleep 1
        kill -KILL "$UNITY_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "[entrypoint-min] Sourcing ROS env..."
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ros2_ws/install/setup.bash

# Restore small shell helpers expected in this environment.
cat > /usr/bin/upp <<'EOS'
#!/bin/bash
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ros2_ws/install/setup.bash
[ -f /opt/dimos-venv/bin/activate ] && source /opt/dimos-venv/bin/activate
EOS
chmod +x /usr/bin/upp

cat > /usr/bin/rosspy <<'EOS'
#!/bin/bash
source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
source /ros2_ws/install/setup.bash
[ -f /opt/dimos-venv/bin/activate ] && source /opt/dimos-venv/bin/activate
if [ -f /workspace/dimos/bin/rosspy.pyz ]; then
    exec python3 /workspace/dimos/bin/rosspy.pyz "$@"
else
    exec python3 -m dimos.utils.cli.rosspy.run_rosspy "$@"
fi
EOS
chmod +x /usr/bin/rosspy

# docker_runner payload mode imports dimos.* modules from Python.
# Keep this minimal: activate venv if present and ensure /workspace/dimos is
# importable even when editable install has not been run yet.
if [ -f "/opt/dimos-venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source /opt/dimos-venv/bin/activate
fi
if [ -d "/workspace/dimos" ]; then
    export PYTHONPATH="/workspace/dimos:${PYTHONPATH:-}"
fi

# Keep DDS config minimal and deterministic.
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
if [ -f "/ros2_ws/config/custom_fastdds.xml" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE=/ros2_ws/config/custom_fastdds.xml
elif [ -f "/ros2_ws/config/fastdds.xml" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE=/ros2_ws/config/fastdds.xml
fi

if [ ! -d "$STACK_ROOT" ]; then
    echo "[entrypoint-min] ERROR: stack root not found: $STACK_ROOT"
    exit 1
fi
cd "$STACK_ROOT"

if [ "$USE_ROUTE_PLANNER" = "true" ]; then
    LAUNCH_FILE="system_simulation_with_route_planner.launch.py"
else
    LAUNCH_FILE="system_simulation.launch.py"
fi

LAUNCH_ARGS="enable_bridge:=false"
if [ "$LOCALIZATION_METHOD" = "fastlio" ]; then
    LAUNCH_ARGS="use_fastlio2:=true ${LAUNCH_ARGS}"
fi

start_unity() {
    if [ ! -f "$UNITY_EXECUTABLE" ]; then
        echo "[entrypoint-min] ERROR: Unity executable not found: $UNITY_EXECUTABLE"
        exit 1
    fi

    # These files are expected by CMU/TARE sim assets. Missing files usually
    # indicate a bad mount and can break downstream map-dependent behavior.
    for required in map.ply traversable_area.ply; do
        if [ ! -f "$UNITY_MESH_DIR/$required" ]; then
            echo "[entrypoint-min] WARNING: missing $UNITY_MESH_DIR/$required"
        fi
    done

    echo "[entrypoint-min] Starting Unity: $UNITY_EXECUTABLE"
    "$UNITY_EXECUTABLE" &
    UNITY_PID=$!
    echo "[entrypoint-min] Unity PID: $UNITY_PID"
}

start_ros_nav_stack() {
    setsid bash -c "
        source /opt/ros/${ROS_DISTRO:-humble}/setup.bash
        source /ros2_ws/install/setup.bash
        cd ${STACK_ROOT}
        ros2 launch vehicle_simulator ${LAUNCH_FILE} ${LAUNCH_ARGS}
    " &
    ROS_NAV_PID=$!
    echo "[entrypoint-min] ROS nav stack PID: $ROS_NAV_PID"
}

stop_ros_nav_stack() {
    if [ -n "$ROS_NAV_PID" ] && kill -0 "$ROS_NAV_PID" 2>/dev/null; then
        kill -TERM "-$ROS_NAV_PID" 2>/dev/null || kill -TERM "$ROS_NAV_PID" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            kill -0 "$ROS_NAV_PID" 2>/dev/null || break
            sleep 1
        done
        kill -KILL "-$ROS_NAV_PID" 2>/dev/null || kill -KILL "$ROS_NAV_PID" 2>/dev/null || true
    fi
}

has_established_bridge_tcp() {
    if ! command -v ss >/dev/null 2>&1; then
        return 0
    fi
    ss -Htn state established '( sport = :10000 or dport = :10000 )' 2>/dev/null | grep -q .
}

unity_topics_ready() {
    local topics
    topics="$(ros2 topic list 2>/dev/null || true)"

    echo "$topics" | grep -Eq '^/registered_scan$' || return 1
    echo "$topics" | grep -Eq '^/camera/image/compressed$' || return 1
    return 0
}

bridge_ready() {
    # Check only that Unity has established the TCP connection to the bridge.
    # unity_topics_ready (ros2 topic list) is intentionally skipped: DDS
    # discovery is too slow/unreliable to use as a readiness gate inside the
    # container — ros2 topic list consistently fails to see Unity bridge topics
    # within any reasonable window even though the publishers ARE registered.
    has_established_bridge_tcp || return 1
    return 0
}

launch_with_retry() {
    local attempt=1

    while true; do
        echo "[entrypoint-min] Launch attempt ${attempt}: ros2 launch vehicle_simulator ${LAUNCH_FILE} ${LAUNCH_ARGS}"
        start_ros_nav_stack

        local deadline=$((SECONDS + UNITY_BRIDGE_CONNECT_TIMEOUT_SEC))
        while [ "$SECONDS" -lt "$deadline" ]; do
            if bridge_ready; then
                echo "[entrypoint-min] Unity bridge ready: /registered_scan and /camera/image/compressed present."
                return 0
            fi

            if ! kill -0 "$ROS_NAV_PID" 2>/dev/null; then
                echo "[entrypoint-min] ROS nav stack exited during bridge startup."
                break
            fi
            sleep 1
        done

        cat <<EOM
================================================================================
================================================================================
==================== UNITY BRIDGE STARTUP TIMEOUT ERROR ========================
================================================================================
[entrypoint-min] Attempt ${attempt} exceeded UNITY_BRIDGE_CONNECT_TIMEOUT_SEC=${UNITY_BRIDGE_CONNECT_TIMEOUT_SEC}
[entrypoint-min] Bridge did not become ready in time.
[entrypoint-min] Required topics missing: /registered_scan and /camera/image/compressed
[entrypoint-min] Stopping ROS nav stack and retrying in ${UNITY_BRIDGE_RETRY_INTERVAL_SEC}s.
================================================================================
================================================================================
EOM

        stop_ros_nav_stack
        attempt=$((attempt + 1))
        sleep "$UNITY_BRIDGE_RETRY_INTERVAL_SEC"
    done
}

case "$MODE" in
    simulation|unity_sim|"")
        start_unity
        launch_with_retry
        ;;
    *)
        echo "[entrypoint-min] MODE=$MODE is non-simulation; launching ROS nav stack once."
        start_ros_nav_stack
        ;;
esac

if [ "$MODE" = "simulation" ] || [ "$MODE" = "unity_sim" ] || [ -z "$MODE" ]; then
    if [ "${USE_RVIZ:-false}" = "true" ]; then
        ros2 run rviz2 rviz2 -d src/route_planner/far_planner/rviz/default.rviz &
    fi
fi

# Keep compatibility with DockerModule runner when payload args are provided.
if [ "$#" -gt 0 ]; then
    # If dimos import still fails, do a one-time editable install fallback.
    if ! python -c "import dimos.navigation.rosnav_docker" >/dev/null 2>&1; then
        if [ -d "/workspace/dimos" ]; then
            echo "[entrypoint-min] dimos not importable; running pip install -e /workspace/dimos"
            pip install -e /workspace/dimos >/tmp/dimos_pip_install.log 2>&1 || {
                echo "[entrypoint-min] WARNING: pip install -e failed; see /tmp/dimos_pip_install.log"
            }
        fi
    fi
    exec python -m dimos.core.docker_runner run "$@"
fi

# Otherwise keep container alive with the nav stack process.
wait "$ROS_NAV_PID"
