"""
Core Ballistics Engine — Full 6DOF-lite Point Mass Simulation

Simulates projectile trajectory with:
  1. Gravity
  2. Aerodynamic drag (G7 table-based, velocity-dependent Cd)
  3. Wind deflection
  4. Magnus effect (spin drift / gyroscopic drift)
  5. Coriolis effect (Earth rotation)
  6. Air density variations (temperature, pressure, humidity, altitude)

Uses 4th-order Runge-Kutta (RK4) integration for accuracy.
Hot path uses pure-Python math (no numpy) for minimal overhead
on 3-element vectors.

Coordinate system (ENU - East-North-Up):
  X = East
  Y = North
  Z = Up

The turret is at origin (0, 0, 0).
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time

from .tables import DragModel, PROJECTILE_50BMG
from .atmosphere import AtmosphereModel, WeatherConditions


# Earth rotation rate (rad/s)
EARTH_OMEGA = 7.2921159e-5

# Default firing latitude (affects Coriolis)
DEFAULT_LATITUDE_DEG = 45.0

# Gravity constant tuple (never allocate)
_GRAVITY = (0.0, 0.0, -9.80665)


@dataclass
class ProjectileState:
    """State of a projectile at a point in time."""
    position: np.ndarray      # [x, y, z] meters (ENU)
    velocity: np.ndarray      # [vx, vy, vz] m/s (ENU)
    time: float               # seconds since fire
    speed: float = 0.0        # scalar speed m/s
    mach: float = 0.0         # Mach number
    alive: bool = True        # still in flight

    def __post_init__(self):
        self.speed = float(np.linalg.norm(self.velocity))


@dataclass
class TrajectoryPoint:
    """Recorded point along the trajectory for visualization."""
    position: np.ndarray
    velocity: np.ndarray
    time: float
    mach: float
    speed: float


@dataclass
class ProjectileTrajectory:
    """Complete trajectory of a fired projectile."""
    points: List[TrajectoryPoint] = field(default_factory=list)
    hit: bool = False
    hit_position: Optional[np.ndarray] = None
    final_time: float = 0.0
    max_range: float = 0.0
    projectile_id: int = 0

    max_trail_points: int = 60  # Rolling window for tracer rendering

    def add_point(self, state: ProjectileState):
        self.points.append(TrajectoryPoint(
            position=state.position.copy(),
            velocity=state.velocity.copy(),
            time=state.time,
            mach=state.mach,
            speed=state.speed,
        ))
        # Keep rolling window for active projectiles
        if len(self.points) > self.max_trail_points:
            self.points = self.points[-self.max_trail_points:]


def _segment_point_distance(a: np.ndarray, b: np.ndarray, p: np.ndarray) -> float:
    """Shortest distance from point *p* to line segment *a*-*b*."""
    ab = b - a
    ab_sq = np.dot(ab, ab)
    if ab_sq < 1e-12:
        return float(np.linalg.norm(p - a))
    t = np.clip(np.dot(p - a, ab) / ab_sq, 0.0, 1.0)
    closest = a + t * ab
    return float(np.linalg.norm(p - closest))


# =========================================================
# Pure-Python 3-vector helpers (used in hot path)
# Avoid numpy overhead for tiny 3-element operations.
# =========================================================

def _vec_norm(v0, v1, v2):
    """Magnitude of 3-vector given as 3 floats."""
    return math.sqrt(v0 * v0 + v1 * v1 + v2 * v2)


class BallisticsEngine:
    """
    Full ballistics simulation engine.

    Uses point-mass model with empirical corrections for:
    - Spin drift (Magnus effect approximation)
    - Coriolis deflection
    - Variable air density with altitude
    """

    def __init__(self,
                 drag_model: str = "G7",
                 latitude_deg: float = DEFAULT_LATITUDE_DEG,
                 dt: float = 0.001):  # 1ms time step for accuracy
        """
        Args:
            drag_model: "G1" or "G7"
            latitude_deg: Firing latitude for Coriolis calculation
            dt: Integration time step in seconds
        """
        self.drag = DragModel(drag_model)
        self.projectile = PROJECTILE_50BMG.copy()
        self.atmosphere = AtmosphereModel()
        self.latitude_rad = math.radians(latitude_deg)
        self.dt = dt

        # Precompute Coriolis vector components
        self._update_coriolis()

        # Spin parameters for Magnus/spin drift
        self._compute_spin_rate()

        # Precompute constants used in drag (avoid dict lookups in hot path)
        self._form_factor = self.projectile["form_factor_g7"] if self.drag.model == "G7" \
                            else self.projectile["form_factor_g1"]
        self._cross_section = self.projectile["cross_section_m2"]
        self._mass = self.projectile["mass_kg"]
        # Combined constant: 0.5 * A / m * form_factor
        self._drag_const = 0.5 * self._cross_section / self._mass * self._form_factor

        # Cached speed of sound (updated via set_weather)
        self._inv_sos = 1.0 / self.atmosphere.speed_of_sound

        # Active projectiles
        self.projectiles: List[Tuple[ProjectileState, ProjectileTrajectory]] = []
        self._next_id = 0

        # Visualization recording interval (record every N steps)
        self.record_interval = 10  # every 10ms at dt=0.001

    def set_weather(self, weather: WeatherConditions):
        """Update atmospheric conditions."""
        self.atmosphere.set_weather(weather)
        self._inv_sos = 1.0 / self.atmosphere.speed_of_sound

    def _update_coriolis(self):
        """
        Precompute Earth rotation vector in ENU coordinates.

        Ω_ENU = ω * (0, cos(lat), sin(lat))
        """
        self.omega_enu = EARTH_OMEGA * np.array([
            0.0,
            np.cos(self.latitude_rad),
            np.sin(self.latitude_rad)
        ])
        # Store as plain floats for hot path
        self._omega0 = 0.0
        self._omega1 = EARTH_OMEGA * math.cos(self.latitude_rad)
        self._omega2 = EARTH_OMEGA * math.sin(self.latitude_rad)

    def _compute_spin_rate(self):
        """
        Compute projectile spin rate from twist rate and muzzle velocity.
        """
        twist_m = self.projectile["twist_rate_inches"] * 0.0254
        v0 = self.projectile["muzzle_velocity_mps"]
        self.initial_spin_rate = 2 * math.pi * v0 / twist_m
        self.spin_direction = self.projectile["twist_direction"]

    # =========================================================
    # HOT PATH — Pure Python math, no numpy allocations
    # All vectors are passed as 3 separate floats.
    # Returns tuples of floats.
    # =========================================================

    def _drag_accel(self, vx, vy, vz, pz, wx, wy, wz):
        """
        Compute drag deceleration (3 floats).

        F_drag = -0.5 * rho * v_rel² * Cd(M) * A * (v_rel/|v_rel|)
        a_drag = F_drag / m
        """
        # Velocity relative to air mass
        rx = vx - wx
        ry = vy - wy
        rz = vz - wz
        speed_rel = math.sqrt(rx * rx + ry * ry + rz * rz)

        if speed_rel < 0.1:
            return 0.0, 0.0, 0.0

        # Air density at projectile altitude (LUT O(1))
        alt = pz if pz > 0.0 else 0.0
        rho = self.atmosphere.density_at_altitude(alt)

        # Mach number and Cd lookup (O(1) dense table)
        mach = speed_rel * self._inv_sos
        cd_ref = self.drag.get_cd(mach)

        # drag_mag = 0.5 * rho * speed_rel * Cd * form_factor * A / m
        # Precomputed: _drag_const = 0.5 * A / m * form_factor
        drag_mag = rho * speed_rel * cd_ref * self._drag_const

        # Drag opposes relative velocity: -drag_mag * v_rel
        return -drag_mag * rx, -drag_mag * ry, -drag_mag * rz

    def _coriolis_accel(self, vx, vy, vz):
        """
        Coriolis acceleration: a_c = -2 * (Ω × v)
        """
        # Ω = (0, ω1, ω2), v = (vx, vy, vz)
        # Ω × v = (ω1*vz - ω2*vy, ω2*vx - 0*vz, 0*vy - ω1*vx)
        #       = (ω1*vz - ω2*vy, ω2*vx, -ω1*vx)
        cx = self._omega1 * vz - self._omega2 * vy
        cy = self._omega2 * vx
        cz = -self._omega1 * vx
        return -2.0 * cx, -2.0 * cy, -2.0 * cz

    def _spin_drift_accel(self, vx, vy, vz, tof):
        """
        Approximate spin drift (gyroscopic drift / Magnus effect).
        Litz empirical model.
        """
        if tof < 0.001:
            return 0.0, 0.0, 0.0

        v_horiz_mag = math.sqrt(vx * vx + vy * vy)
        if v_horiz_mag < 0.1:
            return 0.0, 0.0, 0.0

        # SG ≈ 1.5 for .50 BMG M33
        # drift_accel = 0.12 * (1.5 + 1.2) * sqrt(tof) = 0.324 * sqrt(tof)
        drift_accel = 0.324 * math.sqrt(tof)

        # Perpendicular direction in horizontal plane (right of travel)
        inv_h = self.spin_direction / v_horiz_mag
        # perp = (vy/|v_h|, -vx/|v_h|, 0) * spin_direction
        return vy * inv_h * drift_accel, -vx * inv_h * drift_accel, 0.0

    def _derivatives(self, px, py, pz, vx, vy, vz, t, wx, wy, wz):
        """
        Compute derivatives for RK4.
        Returns (dpx, dpy, dpz, dvx, dvy, dvz).

        dpx/dt = vx, dpy/dt = vy, dpz/dt = vz
        dvx/dt = sum of all accelerations (x component), etc.
        """
        # Gravity (constant)
        ax = 0.0
        ay = 0.0
        az = -9.80665

        # Drag
        dx, dy, dz = self._drag_accel(vx, vy, vz, pz, wx, wy, wz)
        ax += dx
        ay += dy
        az += dz

        # Coriolis
        cx, cy, cz = self._coriolis_accel(vx, vy, vz)
        ax += cx
        ay += cy
        az += cz

        # Spin drift
        sx, sy, sz = self._spin_drift_accel(vx, vy, vz, t)
        ax += sx
        ay += sy
        az += sz

        return vx, vy, vz, ax, ay, az

    def _rk4_step_fast(self, px, py, pz, vx, vy, vz, t, dt, wx, wy, wz):
        """
        RK4 integration step using scalar math.
        Returns (new_px, new_py, new_pz, new_vx, new_vy, new_vz).
        """
        hdt = 0.5 * dt
        t_half = t + hdt

        # k1
        dp1x, dp1y, dp1z, dv1x, dv1y, dv1z = self._derivatives(
            px, py, pz, vx, vy, vz, t, wx, wy, wz)

        # k2
        dp2x, dp2y, dp2z, dv2x, dv2y, dv2z = self._derivatives(
            px + hdt * dp1x, py + hdt * dp1y, pz + hdt * dp1z,
            vx + hdt * dv1x, vy + hdt * dv1y, vz + hdt * dv1z,
            t_half, wx, wy, wz)

        # k3
        dp3x, dp3y, dp3z, dv3x, dv3y, dv3z = self._derivatives(
            px + hdt * dp2x, py + hdt * dp2y, pz + hdt * dp2z,
            vx + hdt * dv2x, vy + hdt * dv2y, vz + hdt * dv2z,
            t_half, wx, wy, wz)

        # k4
        dp4x, dp4y, dp4z, dv4x, dv4y, dv4z = self._derivatives(
            px + dt * dp3x, py + dt * dp3y, pz + dt * dp3z,
            vx + dt * dv3x, vy + dt * dv3y, vz + dt * dv3z,
            t + dt, wx, wy, wz)

        # Combine: new = old + (dt/6) * (k1 + 2*k2 + 2*k3 + k4)
        s = dt / 6.0
        new_px = px + s * (dp1x + 2.0 * dp2x + 2.0 * dp3x + dp4x)
        new_py = py + s * (dp1y + 2.0 * dp2y + 2.0 * dp3y + dp4y)
        new_pz = pz + s * (dp1z + 2.0 * dp2z + 2.0 * dp3z + dp4z)
        new_vx = vx + s * (dv1x + 2.0 * dv2x + 2.0 * dv3x + dv4x)
        new_vy = vy + s * (dv1y + 2.0 * dv2y + 2.0 * dv3y + dv4y)
        new_vz = vz + s * (dv1z + 2.0 * dv2z + 2.0 * dv3z + dv4z)

        return new_px, new_py, new_pz, new_vx, new_vy, new_vz

    # =========================================================
    # PUBLIC API
    # =========================================================

    def fire(self, azimuth_rad: float, elevation_rad: float,
             muzzle_offset: np.ndarray = None,
             dispersion_moa: float = 2.0) -> int:
        """
        Fire a projectile.

        Args:
            azimuth_rad: Horizontal angle (0 = North/+Y, π/2 = East/+X)
            elevation_rad: Vertical angle above horizontal
            muzzle_offset: Position offset from turret center (barrel tip)
            dispersion_moa: Mechanical dispersion in minutes of angle

        Returns:
            Projectile ID for tracking
        """
        v0 = self.projectile["muzzle_velocity_mps"]

        # Convert spherical to Cartesian velocity
        cos_el = math.cos(elevation_rad)
        sin_el = math.sin(elevation_rad)
        vx = v0 * cos_el * math.sin(azimuth_rad)  # East
        vy = v0 * cos_el * math.cos(azimuth_rad)   # North
        vz = v0 * sin_el                            # Up

        # Apply mechanical dispersion (random angular offset)
        if dispersion_moa > 0:
            disp_rad = dispersion_moa / 60.0 * math.pi / 180.0
            disp_az = np.random.normal(0, disp_rad / 2)
            disp_el = np.random.normal(0, disp_rad / 2)
            vx += v0 * disp_az * cos_el
            vz += v0 * disp_el

        velocity = np.array([vx, vy, vz])
        position = muzzle_offset if muzzle_offset is not None else np.array([0.0, 0.0, 1.5])

        state = ProjectileState(
            position=position.copy(),
            velocity=velocity.copy(),
            time=0.0,
            speed=v0,
            mach=self.atmosphere.get_mach(v0),
            alive=True,
        )

        trajectory = ProjectileTrajectory(projectile_id=self._next_id)
        trajectory.add_point(state)

        self.projectiles.append((state, trajectory))
        pid = self._next_id
        self._next_id += 1

        return pid

    def step(self, dt_total: float = None) -> List[Tuple[int, ProjectileState]]:
        """
        Advance all projectiles by dt_total seconds.
        Uses internal dt for sub-stepping with adaptive step size.

        Returns list of (id, state) for all active projectiles.
        """
        if dt_total is None:
            dt_total = self.dt

        # Wind as scalars (avoid property + np.array each call)
        w = self.atmosphere.weather.wind_vector
        wx, wy, wz = float(w[0]), float(w[1]), float(w[2])

        inv_sos = self._inv_sos
        base_dt = self.dt
        results = []

        for i, (state, traj) in enumerate(self.projectiles):
            if not state.alive:
                continue

            # Unpack state to scalars for hot loop
            px, py, pz = float(state.position[0]), float(state.position[1]), float(state.position[2])
            vx, vy, vz = float(state.velocity[0]), float(state.velocity[1]), float(state.velocity[2])
            t = state.time
            spd = state.speed

            remaining = dt_total
            step_count = 0

            alive = True
            while remaining > 1e-7:
                # Adaptive time step based on Mach regime
                mach = spd * inv_sos
                if mach > 1.15 or mach < 0.88:
                    dt_step = min(0.002, remaining)    # supersonic / subsonic
                elif spd < 100.0:
                    dt_step = min(0.005, remaining)    # very slow
                else:
                    dt_step = min(base_dt, remaining)  # transonic: full precision

                new_px, new_py, new_pz, new_vx, new_vy, new_vz = \
                    self._rk4_step_fast(px, py, pz, vx, vy, vz, t, dt_step, wx, wy, wz)

                px, py, pz = new_px, new_py, new_pz
                vx, vy, vz = new_vx, new_vy, new_vz
                t += dt_step
                spd = math.sqrt(vx * vx + vy * vy + vz * vz)

                remaining -= dt_step
                step_count += 1

                # Record trajectory point periodically
                if step_count % self.record_interval == 0:
                    # Write back to state temporarily for add_point
                    state.position[0] = px
                    state.position[1] = py
                    state.position[2] = pz
                    state.velocity[0] = vx
                    state.velocity[1] = vy
                    state.velocity[2] = vz
                    state.time = t
                    state.speed = spd
                    state.mach = mach
                    traj.add_point(state)

                # Check termination conditions
                if pz < -10.0:  # Below ground
                    alive = False
                    break

                if spd < 50.0:  # Effectively stopped
                    alive = False
                    break

                if t > 30.0:  # Max flight time 30s
                    alive = False
                    break

                # Max range check (horizontal)
                if px * px + py * py > 49000000.0:  # 7000² = 49_000_000
                    alive = False
                    break

            # Write back scalar state to numpy arrays
            state.position[0] = px
            state.position[1] = py
            state.position[2] = pz
            state.velocity[0] = vx
            state.velocity[1] = vy
            state.velocity[2] = vz
            state.time = t
            state.speed = spd
            state.mach = spd * inv_sos
            state.alive = alive

            if not alive:
                traj.final_time = t

            results.append((traj.projectile_id, state))

        return results

    def check_hit(self, projectile_id: int, target_pos: np.ndarray,
                   target_radius: float) -> bool:
        """
        Check if a projectile has hit a spherical target.
        """
        for state, traj in self.projectiles:
            if traj.projectile_id == projectile_id and state.alive:
                dist = np.linalg.norm(state.position - target_pos)
                if dist <= target_radius:
                    state.alive = False
                    traj.hit = True
                    traj.hit_position = state.position.copy()
                    traj.final_time = state.time
                    return True
        return False

    def check_all_hits(self, target_pos: np.ndarray,
                        target_radius: float) -> List[int]:
        """Check all active projectiles against a target. Returns hit IDs.

        Uses swept-sphere: checks closest point on the line segment between
        the projectile's previous and current position to catch fast bullets
        that pass through the target between frames.
        """
        hits = []
        for state, traj in self.projectiles:
            if not state.alive:
                continue
            # Swept check: use last two trajectory points
            if len(traj.points) >= 2:
                p0 = traj.points[-2].position
                p1 = state.position
                dist = _segment_point_distance(p0, p1, target_pos)
            else:
                dist = np.linalg.norm(state.position - target_pos)
            if dist <= target_radius:
                state.alive = False
                traj.hit = True
                traj.hit_position = state.position.copy()
                traj.final_time = state.time
                hits.append(traj.projectile_id)
        return hits

    def get_active_projectiles(self) -> List[Tuple[int, np.ndarray, np.ndarray]]:
        """Get positions and velocities of all active projectiles."""
        active = []
        for state, traj in self.projectiles:
            if state.alive:
                active.append((traj.projectile_id,
                              state.position.copy(),
                              state.velocity.copy()))
        return active

    def get_tracer_trails(self) -> List[List[np.ndarray]]:
        """Get trail positions for all active projectiles (for tracer rendering)."""
        trails = []
        for state, traj in self.projectiles:
            if state.alive and len(traj.points) >= 2:
                trails.append([pt.position for pt in traj.points])
        return trails

    def cleanup_dead(self, max_dead: int = 100):
        """Remove old dead projectiles, keeping trajectories for visualization."""
        dead = [(s, t) for s, t in self.projectiles if not s.alive]
        alive = [(s, t) for s, t in self.projectiles if s.alive]

        if len(dead) > max_dead:
            dead = dead[-max_dead:]  # Keep most recent

        self.projectiles = alive + dead

    def clear_all(self):
        """Remove all projectiles."""
        self.projectiles.clear()


def test_ballistics():
    """Quick validation of ballistics engine."""
    engine = BallisticsEngine(drag_model="G7")

    # Fire at 45° elevation (maximum range test)
    pid = engine.fire(azimuth_rad=0, elevation_rad=np.radians(45), dispersion_moa=0)

    print(f"Projectile fired: id={pid}")
    print(f"Muzzle velocity: {PROJECTILE_50BMG['muzzle_velocity_mps']} m/s")
    print(f"Air density: {engine.atmosphere.air_density:.4f} kg/m³")
    print(f"Speed of sound: {engine.atmosphere.speed_of_sound:.1f} m/s")
    print(f"Initial Mach: {engine.atmosphere.get_mach(890):.3f}")
    print()

    # Simulate
    t_start = time.time()
    max_alt = 0
    final_state = None
    while True:
        results = engine.step(0.01)  # 10ms steps
        if not results:
            break
        pid, state = results[0]
        max_alt = max(max_alt, state.position[2])
        if not state.alive:
            final_state = state
            break

    t_elapsed = time.time() - t_start

    if final_state:
        p = final_state.position
        range_m = math.sqrt(p[0]**2 + p[1]**2)
        print(f"Final range: {range_m:.0f} m")
        print(f"Max altitude: {max_alt:.0f} m")
        print(f"Time of flight: {final_state.time:.2f} s")
        print(f"Final speed: {final_state.speed:.0f} m/s (Mach {final_state.mach:.2f})")
        print(f"Simulation time: {t_elapsed*1000:.1f} ms")

    # Test at 5° elevation (typical AA engagement)
    engine.clear_all()
    pid2 = engine.fire(azimuth_rad=0, elevation_rad=np.radians(5), dispersion_moa=0)

    while True:
        results = engine.step(0.01)
        if not results:
            break
        pid, state = results[0]
        if not state.alive:
            break

    p = state.position
    range_m = math.sqrt(p[0]**2 + p[1]**2)
    print(f"\n5° elevation shot:")
    print(f"Range: {range_m:.0f} m, TOF: {state.time:.2f}s, "
          f"Final speed: {state.speed:.0f} m/s")


if __name__ == "__main__":
    test_ballistics()
