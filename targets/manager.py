"""
Target Manager — Aerial Target Spawning and Tracking

Generates Shahed-136 (Geran-2) targets with realistic flight parameters:
  - Based on real Shahed-136 specifications
  - Straight-line trajectories at constant speed
  - Spawn at configurable ranges and altitudes
  - One target at a time (round-based)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from enum import Enum


class TargetType(Enum):
    SHAHED_136 = "shahed_136"


@dataclass
class TargetProfile:
    """Physical and flight characteristics of a target type."""
    name: str
    target_type: TargetType
    speed_range: Tuple[float, float]  # m/s (min, max)
    altitude_range: Tuple[float, float]  # meters (min, max)
    size_m: float  # approximate wingspan/size for collision
    hit_radius: float  # radius for hit detection (meters)
    
    # Visual properties
    model_scale: float = 1.0
    color: Tuple[float, float, float] = (0.8, 0.2, 0.2)


# Shahed-136 / Geran-2 — real specifications from OSINT
# See assets/shahed/SPECIFICATIONS.md for full details
TARGET_PROFILES = {
    TargetType.SHAHED_136: TargetProfile(
        name="Shahed-136",
        target_type=TargetType.SHAHED_136,
        speed_range=(19, 51),        # 70-185 km/h (min observed to max)
        altitude_range=(60, 2000),   # Low approach to cruise altitude
        size_m=2.5,                  # Wingspan 2.5m
        hit_radius=1.75,             # Length 3.5m / 2
        model_scale=1.0,
        color=(0.35, 0.35, 0.30),   # Olive-grey composite
    ),
}


@dataclass
class Target:
    """Active target instance."""
    target_id: int
    profile: TargetProfile
    position: np.ndarray       # Current position [x, y, z] (ENU)
    velocity: np.ndarray       # Constant velocity vector [vx, vy, vz]
    spawn_position: np.ndarray # Where it appeared
    speed: float               # Scalar speed m/s
    alive: bool = True
    time_alive: float = 0.0
    
    @property
    def altitude(self) -> float:
        return self.position[2]
    
    @property
    def range_from_origin(self) -> float:
        return float(np.linalg.norm(self.position))
    
    @property
    def horizontal_range(self) -> float:
        return float(np.sqrt(self.position[0]**2 + self.position[1]**2))
    
    def get_bearing_elevation(self) -> Tuple[float, float]:
        """Get bearing and elevation from turret to target."""
        dx, dy, dz = self.position
        bearing = np.arctan2(dx, dy)  # azimuth
        h_dist = np.sqrt(dx**2 + dy**2)
        elev = np.arctan2(dz, h_dist)
        return bearing, elev


class TargetManager:
    """Manages spawning and tracking of aerial targets."""
    
    def __init__(self):
        self._next_id = 0
        self.active_target: Optional[Target] = None
        self.spawn_range = (800, 3000)    # How far to spawn targets
        self.pass_range = 5000             # Target disappears at this range
        self.min_approach_dist = 200       # Closest approach distance
        
        # Difficulty progression
        self.difficulty = 1  # 1-10
    
    def spawn_target(self, target_type: TargetType = None,
                      forced_params: dict = None) -> Target:
        """
        Spawn a new aerial target.
        
        Target flies in a straight line, crossing somewhere near the turret.
        Spawn on a sphere around turret, exit on opposite side.
        """
        if self.active_target and self.active_target.alive:
            self.active_target.alive = False
        
        # Default to Shahed-136
        if target_type is None:
            target_type = TargetType.SHAHED_136
        
        profile = TARGET_PROFILES[target_type]
        
        # Random speed within profile range
        speed = np.random.uniform(*profile.speed_range)
        
        # Random altitude within profile range
        altitude = np.random.uniform(*profile.altitude_range)
        
        # Spawn position: random direction at spawn_range distance
        spawn_bearing = np.random.uniform(0, 2 * np.pi)
        spawn_dist = np.random.uniform(*self.spawn_range)
        
        spawn_x = spawn_dist * np.sin(spawn_bearing)
        spawn_y = spawn_dist * np.cos(spawn_bearing)
        spawn_z = altitude
        spawn_pos = np.array([spawn_x, spawn_y, spawn_z])
        
        # Flight direction: toward a point near origin (with some offset)
        # This ensures target passes near the turret
        aim_offset = np.random.uniform(
            -self.min_approach_dist * 2,
            self.min_approach_dist * 2,
            size=2
        )
        aim_point = np.array([aim_offset[0], aim_offset[1], altitude])
        
        # Extend flight line through and past aim point
        flight_dir = aim_point - spawn_pos
        flight_dir = flight_dir / np.linalg.norm(flight_dir)
        
        velocity = flight_dir * speed
        
        # Override with forced params if given
        if forced_params:
            if 'speed' in forced_params:
                speed = forced_params['speed']
                velocity = flight_dir * speed
            if 'altitude' in forced_params:
                spawn_pos[2] = forced_params['altitude']
                altitude = forced_params['altitude']
            if 'position' in forced_params:
                spawn_pos = np.array(forced_params['position'])
            if 'velocity' in forced_params:
                velocity = np.array(forced_params['velocity'])
                speed = np.linalg.norm(velocity)
        
        target = Target(
            target_id=self._next_id,
            profile=profile,
            position=spawn_pos.copy(),
            velocity=velocity.copy(),
            spawn_position=spawn_pos.copy(),
            speed=speed,
        )
        
        self._next_id += 1
        self.active_target = target
        return target
    
    def update(self, dt: float) -> Optional[Target]:
        """
        Update target position. Returns target if still active, None if expired.
        """
        if self.active_target is None or not self.active_target.alive:
            return None
        
        t = self.active_target
        t.position += t.velocity * dt
        t.time_alive += dt
        
        # Check if target has left the engagement zone
        if t.horizontal_range > self.pass_range:
            t.alive = False
            return None
        
        # Check if below ground
        if t.position[2] < 0:
            t.alive = False
            return None
        
        # Timeout (2 minutes max)
        if t.time_alive > 120:
            t.alive = False
            return None
        
        return t
    
    def destroy_target(self) -> bool:
        """Mark active target as destroyed."""
        if self.active_target and self.active_target.alive:
            self.active_target.alive = False
            return True
        return False
    
    def get_target_info(self) -> Optional[dict]:
        """Get target info for API/HUD (what a radar would show)."""
        if not self.active_target or not self.active_target.alive:
            return None
        
        t = self.active_target
        bearing, elev = t.get_bearing_elevation()
        
        return {
            "id": t.target_id,
            "type": t.profile.name,
            "position": t.position.tolist(),
            "velocity": t.velocity.tolist(),
            "speed_mps": round(t.speed, 1),
            "altitude_m": round(t.altitude, 1),
            "range_m": round(t.range_from_origin, 1),
            "horizontal_range_m": round(t.horizontal_range, 1),
            "bearing_deg": round(np.degrees(bearing), 1),
            "elevation_deg": round(np.degrees(elev), 1),
            "time_alive": round(t.time_alive, 1),
        }
    
    def get_monocular_view(self, turret_azimuth: float, turret_elevation: float,
                            fov_deg: float = 10.0) -> Optional[dict]:
        """
        Get what the monocular can see.
        Returns target info ONLY if target is within monocular FOV.
        This is the challenge-mode API — scripts can only see through this.
        """
        if not self.active_target or not self.active_target.alive:
            return {"target_visible": False}
        
        t = self.active_target
        bearing, elev = t.get_bearing_elevation()
        
        # Check if target is within monocular FOV
        az_diff = abs(bearing - turret_azimuth)
        az_diff = min(az_diff, 2*np.pi - az_diff)
        el_diff = abs(elev - turret_elevation)
        
        fov_rad = np.radians(fov_deg) / 2
        
        if az_diff > fov_rad or el_diff > fov_rad:
            return {"target_visible": False}
        
        # Target is visible in monocular
        # Provide angular info only (like looking through a scope)
        return {
            "target_visible": True,
            "angular_offset_az_deg": round(np.degrees(bearing - turret_azimuth), 3),
            "angular_offset_el_deg": round(np.degrees(elev - turret_elevation), 3),
            "angular_size_deg": round(np.degrees(2 * np.arctan(
                t.profile.size_m / (2 * t.range_from_origin)
            )), 4),
        }
