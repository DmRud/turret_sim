"""
Turret Model — Browning M2HB (.50 cal) on M3 Tripod

Realistic mechanical properties:
  - Traverse: 360° (±180°), rate ~60°/s with T&E mechanism
  - Elevation: -15° to +85° (AA configuration), rate ~40°/s
  - Rate of fire: 450-600 RPM (cyclic), ~485 RPM typical
  - Feed: 100-round M2 ammunition belt
  - Barrel overheat: sustained fire limit ~200 rounds before barrel change
  - Reload time: ~8 seconds (belt change)
  - Barrel change: ~10 seconds (requires cooling)

Coordinate system:
  Azimuth: 0 = North (+Y), increases clockwise (East = π/2)
  Elevation: 0 = horizontal, positive = up
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Callable
from enum import Enum


class TurretState(Enum):
    READY = "ready"
    FIRING = "firing"
    RELOADING = "reloading"
    OVERHEATED = "overheated"
    BARREL_CHANGE = "barrel_change"


@dataclass
class TurretConfig:
    """M2HB configuration parameters."""
    # Traverse (azimuth)
    azimuth_min_rad: float = -np.pi          # -180°
    azimuth_max_rad: float = np.pi           # +180°
    azimuth_rate_rps: float = np.radians(60) # 60°/s max traverse
    
    # Elevation
    elevation_min_rad: float = np.radians(-15)  # -15° (M3 tripod AA)
    elevation_max_rad: float = np.radians(85)   # +85°
    elevation_rate_rps: float = np.radians(40)  # 40°/s max elevation
    
    # Fire control
    rate_of_fire_rpm: float = 485.0   # Rounds per minute (cyclic)
    belt_capacity: int = 100          # Rounds per belt
    
    # Thermal model
    heat_per_round: float = 1.0       # Arbitrary heat units per round
    heat_dissipation_rate: float = 0.3  # Heat units per second (cooling)
    overheat_threshold: float = 200.0   # Heat level for overheat
    safe_threshold: float = 50.0        # Heat level to resume firing
    barrel_change_time: float = 10.0    # Seconds
    
    # Reload
    reload_time: float = 8.0           # Seconds for belt change
    
    # Physical dimensions (for muzzle position calculation)
    barrel_length_m: float = 1.143      # 45 inches
    mount_height_m: float = 1.2         # Height of receiver above ground
    receiver_length_m: float = 0.4      # Offset from pivot to barrel start
    
    # Twin mount (dual barrels)
    barrel_separation_m: float = 0.15   # Distance between barrels
    is_twin: bool = True


class TurretModel:
    """
    Simulates the mechanical behavior of an M2HB turret.
    """
    
    def __init__(self, config: TurretConfig = None):
        self.config = config or TurretConfig()
        
        # Current orientation
        self.azimuth = 0.0       # radians, 0 = North
        self.elevation = 0.0     # radians, 0 = horizontal
        
        # Target orientation (where we want to point)
        self.target_azimuth = 0.0
        self.target_elevation = 0.0
        
        # State
        self.state = TurretState.READY
        self.ammo_remaining = self.config.belt_capacity
        self.heat_level = 0.0
        self.is_firing = False
        
        # Timing
        self.fire_interval = 60.0 / self.config.rate_of_fire_rpm
        self.time_since_last_shot = 999.0
        self.state_timer = 0.0  # Timer for reload/cooldown states
        
        # Twin barrel alternation
        self._barrel_toggle = False  # Alternates between left/right barrel
        
        # Statistics
        self.total_rounds_fired = 0
        self.belts_used = 0
        
        # Callbacks
        self._on_fire_callback: Optional[Callable] = None
        self._on_event_callback: Optional[Callable] = None
    
    def set_fire_callback(self, callback: Callable):
        """Set callback for when a round is fired. callback(muzzle_pos, azimuth, elevation)"""
        self._on_fire_callback = callback
    
    def set_event_callback(self, callback: Callable):
        """Set callback for events. callback(event_type, data)"""
        self._on_event_callback = callback
    
    def _emit_event(self, event_type: str, data: dict = None):
        if self._on_event_callback:
            self._on_event_callback(event_type, data or {})
    
    def set_target(self, azimuth_rad: float, elevation_rad: float):
        """Set desired turret orientation."""
        self.target_azimuth = np.clip(
            azimuth_rad,
            self.config.azimuth_min_rad,
            self.config.azimuth_max_rad
        )
        self.target_elevation = np.clip(
            elevation_rad,
            self.config.elevation_min_rad,
            self.config.elevation_max_rad
        )
    
    def set_target_direction(self, direction: np.ndarray):
        """Set target from a 3D direction vector (ENU)."""
        dx, dy, dz = direction
        azimuth = np.arctan2(dx, dy)  # atan2(East, North)
        horiz_dist = np.sqrt(dx**2 + dy**2)
        elevation = np.arctan2(dz, horiz_dist)
        self.set_target(azimuth, elevation)
    
    def start_firing(self):
        """Begin continuous fire."""
        if self.state in (TurretState.READY, TurretState.FIRING):
            self.is_firing = True
    
    def stop_firing(self):
        """Cease fire."""
        self.is_firing = False
    
    def reload(self):
        """Initiate reload (belt change)."""
        if self.state != TurretState.RELOADING:
            self.state = TurretState.RELOADING
            self.state_timer = self.config.reload_time
            self.is_firing = False
            self._emit_event("reload_start", {"time": self.config.reload_time})
    
    def get_muzzle_positions(self) -> List[np.ndarray]:
        """
        Get world-space muzzle positions for each barrel.
        Returns list of positions (2 for twin mount, 1 for single).
        """
        positions = []
        
        cos_az = np.cos(self.azimuth)
        sin_az = np.sin(self.azimuth)
        cos_el = np.cos(self.elevation)
        sin_el = np.sin(self.elevation)
        
        # Direction vector
        barrel_dir = np.array([
            cos_el * sin_az,   # East
            cos_el * cos_az,   # North  
            sin_el             # Up
        ])
        
        # Barrel tip position
        barrel_len = self.config.barrel_length_m + self.config.receiver_length_m
        base_pos = np.array([0, 0, self.config.mount_height_m])
        
        if self.config.is_twin:
            # Perpendicular to barrel direction in horizontal plane
            perp = np.array([cos_az, -sin_az, 0.0])
            half_sep = self.config.barrel_separation_m / 2
            
            pos_left = base_pos + barrel_dir * barrel_len - perp * half_sep
            pos_right = base_pos + barrel_dir * barrel_len + perp * half_sep
            positions = [pos_left, pos_right]
        else:
            pos = base_pos + barrel_dir * barrel_len
            positions = [pos]
        
        return positions
    
    def get_active_muzzle_position(self) -> np.ndarray:
        """Get the muzzle position for the next barrel to fire."""
        positions = self.get_muzzle_positions()
        if self.config.is_twin:
            return positions[1 if self._barrel_toggle else 0]
        return positions[0]
    
    def is_on_target(self, tolerance_rad: float = np.radians(0.1)) -> bool:
        """Check if turret is pointing at target within tolerance."""
        az_err = abs(self.azimuth - self.target_azimuth)
        el_err = abs(self.elevation - self.target_elevation)
        return az_err < tolerance_rad and el_err < tolerance_rad
    
    def update(self, dt: float):
        """
        Update turret state for one time step.
        
        Handles:
        - Slewing to target orientation
        - Heat generation/dissipation
        - Firing timing
        - State transitions (reload, overheat, etc.)
        """
        # ---- State machine ----
        if self.state == TurretState.RELOADING:
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.ammo_remaining = self.config.belt_capacity
                self.belts_used += 1
                self.state = TurretState.READY
                self._emit_event("reload_complete", {
                    "ammo": self.ammo_remaining
                })
            # Heat still dissipates during reload
            self.heat_level = max(0, self.heat_level - self.config.heat_dissipation_rate * dt)
            self._update_slew(dt)
            return
        
        if self.state == TurretState.OVERHEATED:
            self.heat_level = max(0, self.heat_level - self.config.heat_dissipation_rate * dt * 1.5)
            if self.heat_level <= self.config.safe_threshold:
                self.state = TurretState.READY
                self._emit_event("overheat_cleared", {"heat": self.heat_level})
            self._update_slew(dt)
            return
        
        if self.state == TurretState.BARREL_CHANGE:
            self.state_timer -= dt
            if self.state_timer <= 0:
                self.heat_level = 0
                self.state = TurretState.READY
                self._emit_event("barrel_change_complete", {})
            return
        
        # ---- Normal operation (READY/FIRING) ----
        
        # Slew to target
        self._update_slew(dt)
        
        # Heat dissipation
        self.heat_level = max(0, self.heat_level - self.config.heat_dissipation_rate * dt)
        
        # Firing logic
        self.time_since_last_shot += dt
        
        if self.is_firing and self.ammo_remaining > 0:
            self.state = TurretState.FIRING
            
            # Check fire rate
            while self.time_since_last_shot >= self.fire_interval:
                self._fire_round()
                self.time_since_last_shot -= self.fire_interval
                
                if self.ammo_remaining <= 0:
                    self.is_firing = False
                    self._emit_event("ammo_depleted", {})
                    self.reload()
                    break
                
                if self.heat_level >= self.config.overheat_threshold:
                    self.is_firing = False
                    self.state = TurretState.OVERHEATED
                    self._emit_event("overheat", {"heat": self.heat_level})
                    break
        else:
            if self.state == TurretState.FIRING:
                self.state = TurretState.READY
    
    def _update_slew(self, dt: float):
        """Move turret toward target at limited rate."""
        # Azimuth
        az_diff = self.target_azimuth - self.azimuth
        # Normalize to [-π, π]
        az_diff = (az_diff + np.pi) % (2 * np.pi) - np.pi
        
        max_az_delta = self.config.azimuth_rate_rps * dt
        if abs(az_diff) > max_az_delta:
            self.azimuth += np.sign(az_diff) * max_az_delta
        else:
            self.azimuth = self.target_azimuth
        
        # Normalize azimuth to [-π, π]
        self.azimuth = (self.azimuth + np.pi) % (2 * np.pi) - np.pi
        
        # Elevation
        el_diff = self.target_elevation - self.elevation
        max_el_delta = self.config.elevation_rate_rps * dt
        if abs(el_diff) > max_el_delta:
            self.elevation += np.sign(el_diff) * max_el_delta
        else:
            self.elevation = self.target_elevation
        
        # Clamp elevation
        self.elevation = np.clip(
            self.elevation,
            self.config.elevation_min_rad,
            self.config.elevation_max_rad
        )
    
    def _fire_round(self):
        """Fire a single round."""
        self.ammo_remaining -= 1
        self.total_rounds_fired += 1
        self.heat_level += self.config.heat_per_round
        
        # Get muzzle position
        muzzle_pos = self.get_active_muzzle_position()
        
        # Toggle barrel for twin mount
        if self.config.is_twin:
            self._barrel_toggle = not self._barrel_toggle
        
        # Fire callback (creates projectile in ballistics engine)
        if self._on_fire_callback:
            self._on_fire_callback(muzzle_pos, self.azimuth, self.elevation)
        
        self._emit_event("round_fired", {
            "ammo": self.ammo_remaining,
            "heat": self.heat_level,
            "total_fired": self.total_rounds_fired,
        })
    
    def get_status(self) -> dict:
        """Get current turret status for API/HUD."""
        return {
            "state": self.state.value,
            "azimuth_deg": np.degrees(self.azimuth),
            "elevation_deg": np.degrees(self.elevation),
            "target_azimuth_deg": np.degrees(self.target_azimuth),
            "target_elevation_deg": np.degrees(self.target_elevation),
            "ammo": self.ammo_remaining,
            "heat": round(self.heat_level, 1),
            "heat_pct": round(self.heat_level / self.config.overheat_threshold * 100, 1),
            "is_firing": self.is_firing,
            "on_target": self.is_on_target(),
            "total_rounds_fired": self.total_rounds_fired,
            "belts_used": self.belts_used,
        }
