# dimos/hardware/kinpy_kinematics.py
# or wherever you want it to live

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import kinpy as kp
import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation as R


class KinpyKinematics:
    """Thin kinpy-based kinematics helper.

    - Loads a URDF and builds a `kinpy.SerialChain` for a given end-effector link.
    - Provides:
        * FK:    q -> (pos, quat_wxyz)
        * IK:    (q_init, target_pos, target_quat_wxyz) -> q_sol
        * J:     jacobian(q)
        * dls:   joint_velocity(q, twist) -> dq  (for velocity controllers)

    It does **not** know about:
        - Piper SDK
        - SO-101 motors
        - dimos Pose / LCM Pose types

    Those wrappers (PiperArm, SO101Arm, etc.) should handle unit conversions and
    Pose <-> (pos, quat) conversions and just call this class.
    """

    def __init__(
        self,
        urdf_path: str | Path,
        ee_link_name: str,
        *,
        max_iters: int = 100,
        tol: float = 1e-4,
        damping: float = 1e-3,
    ) -> None:
        """
        Parameters
        ----------
        urdf_path:
            Path to the URDF file.
        ee_link_name:
            Name of the end-effector link as defined in the URDF.
        max_iters:
            Maximum number of iterations for iterative IK.
        tol:
            Pose error tolerance (position in meters, orientation via rot-vector).
        damping:
            Damping λ for damped least-squares IK / velocity control.
        """
        urdf_path = Path(urdf_path)
        with urdf_path.open("r") as f:
            self._chain = kp.build_serial_chain_from_urdf(f, ee_link_name)

        self.joint_names: list[str] = self._chain.get_joint_parameter_names()
        self.dof: int = len(self.joint_names)

        self._max_iters = int(max_iters)
        self._tol = float(tol)
        self._damping = float(damping)

    # ------------------------------------------------------------------
    # Forward Kinematics
    # ------------------------------------------------------------------
    def fk(self, q: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Forward kinematics: joint vector -> (position, quaternion_wxyz)."""
        q = np.asarray(q, dtype=float).reshape(-1)
        if q.shape[0] != self.dof:
            raise ValueError(f"Expected {self.dof} DoF, got {q.shape[0]}")

        tf: kp.Transform = self._chain.forward_kinematics(q, end_only=True)
        pos = np.asarray(tf.pos, dtype=float)          # shape (3,)
        quat_wxyz = np.asarray(tf.rot, dtype=float)    # shape (4,), [w, x, y, z]

        return pos, quat_wxyz

    # ------------------------------------------------------------------
    # Inverse Kinematics
    # ------------------------------------------------------------------
    def ik(
        self,
        q_init: NDArray[np.float64],
        target_pos: NDArray[np.float64],
        target_quat_wxyz: NDArray[np.float64],
        active_mask: NDArray[np.bool_] | None = None,
    ) -> NDArray[np.float64]:
        """Iterative IK using damped least squares.

        Parameters
        ----------
        q_init:
            Initial joint configuration, shape (dof,).
        target_pos:
            Target position in world frame, shape (3,).
        target_quat_wxyz:
            Target orientation quaternion (w, x, y, z), shape (4,).
        active_mask:
            Optional boolean mask of shape (dof,) indicating which joints
            are allowed to move. If None, all joints are active.

        Returns
        -------
        q_sol:
            Joint vector of shape (dof,) in the same order as `joint_names`.
        """
        q = np.asarray(q_init, dtype=float).reshape(-1)
        if q.shape[0] != self.dof:
            raise ValueError(f"Expected {self.dof} DoF, got {q.shape[0]}")

        target_pos = np.asarray(target_pos, dtype=float).reshape(3)
        target_quat_wxyz = np.asarray(target_quat_wxyz, dtype=float).reshape(4)

        target_tf = kp.Transform(pos=target_pos, rot=target_quat_wxyz)

        if active_mask is None:
            mask = np.ones(self.dof, dtype=bool)
        else:
            mask = np.asarray(active_mask, dtype=bool).reshape(-1)
            if mask.shape[0] != self.dof:
                raise ValueError(
                    f"active_mask must have length {self.dof}, got {mask.shape[0]}"
                )

        lam = self._damping

        for _ in range(self._max_iters):
            current_tf: kp.Transform = self._chain.forward_kinematics(q, end_only=True)

            # Position error
            e_pos = target_tf.pos - current_tf.pos  # (3,)

            # Orientation error via quaternion difference (wxyz)
            q_t = np.asarray(target_tf.rot, dtype=float)
            q_c = np.asarray(current_tf.rot, dtype=float)
            q_err = self._quat_multiply(q_t, self._quat_conjugate(q_c))

            w, x, y, z = q_err
            # Small-angle approximation: rotation vector ≈ 2 * sign(w) * v
            e_rot = 2.0 * np.sign(w) * np.array([x, y, z], dtype=float)

            err = np.concatenate([e_pos, e_rot])  # (6,)
            if np.linalg.norm(err) < self._tol:
                break

            # 6 x n Jacobian
            J_full = np.asarray(self._chain.jacobian(q), dtype=float)
            J = J_full[:, mask]  # 6 x n_active

            JT = J.T  # n_active x 6
            JJt = J @ JT  # 6 x 6
            A = JJt + (lam**2) * np.eye(6, dtype=float)

            dq_active = JT @ np.linalg.solve(A, err)

            dq = np.zeros_like(q)
            dq[mask] = dq_active
            q = q + dq

        # Ensure frozen joints stay at initial value
        q[~mask] = q_init[~mask]
        return q

    # ------------------------------------------------------------------
    # Jacobian & velocity-level control
    # ------------------------------------------------------------------
    def jacobian(self, q: NDArray[np.float64]) -> NDArray[np.float64]:
        """Return the 6 x dof geometric Jacobian at configuration q."""
        q = np.asarray(q, dtype=float).reshape(-1)
        if q.shape[0] != self.dof:
            raise ValueError(f"Expected {self.dof} DoF, got {q.shape[0]}")
        return np.asarray(self._chain.jacobian(q), dtype=float)

    def joint_velocity(
        self,
        q: NDArray[np.float64],
        twist: NDArray[np.float64],
        active_mask: NDArray[np.bool_] | None = None,
    ) -> NDArray[np.float64]:
        """Compute joint velocities dq for a desired 6D twist using DLS.

        Parameters
        ----------
        q:
            Joint configuration (dof,).
        twist:
            6D end-effector twist [vx, vy, vz, wx, wy, wz] (same convention
            as `jacobian(q)`).
        active_mask:
            Optional boolean mask for which joints can move.

        Returns
        -------
        dq:
            Joint velocities (dof,).
        """
        q = np.asarray(q, dtype=float).reshape(-1)
        if q.shape[0] != self.dof:
            raise ValueError(f"Expected {self.dof} DoF, got {q.shape[0]}")

        twist = np.asarray(twist, dtype=float).reshape(6)

        if active_mask is None:
            mask = np.ones(self.dof, dtype=bool)
        else:
            mask = np.asarray(active_mask, dtype=bool).reshape(-1)
            if mask.shape[0] != self.dof:
                raise ValueError(
                    f"active_mask must have length {self.dof}, got {mask.shape[0]}"
                )

        J_full = np.asarray(self._chain.jacobian(q), dtype=float)  # 6 x dof
        J = J_full[:, mask]  # 6 x n_active

        JT = J.T  # n_active x 6
        JJt = J @ JT  # 6 x 6
        A = JJt + (self._damping**2) * np.eye(6, dtype=float)

        dq_active = JT @ np.linalg.solve(A, twist)

        dq = np.zeros_like(q)
        dq[mask] = dq_active
        return dq

    # ------------------------------------------------------------------
    # Quaternion helpers (w, x, y, z)
    # ------------------------------------------------------------------
    @staticmethod
    def _quat_conjugate(q: Sequence[float]) -> NDArray[np.float64]:
        q = np.asarray(q, dtype=float)
        return np.array([q[0], -q[1], -q[2], -q[3]], dtype=float)

    @staticmethod
    def _quat_multiply(
        q1: Sequence[float],
        q2: Sequence[float],
    ) -> NDArray[np.float64]:
        """Hamilton product of quaternions (w, x, y, z) using SciPy."""
        q1 = np.asarray(q1, dtype=float)
        q2 = np.asarray(q2, dtype=float)

        if q1.shape != (4,) or q2.shape != (4,):
            raise ValueError(
                f"Expected quaternions of shape (4,), got {q1.shape} and {q2.shape}"
            )

        # Interpret input as scalar-first (w, x, y, z)
        r1 = R.from_quat(q1, scalar_first=True)
        r2 = R.from_quat(q2, scalar_first=True)

        # Composition: r = r1 * r2  (Hamilton product q1 ⊗ q2)
        r = r1 * r2

        # Return as scalar-first (w, x, y, z)
        q_wxyz = r.as_quat(scalar_first=True)
        return np.asarray(q_wxyz, dtype=float)
