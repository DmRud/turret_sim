"""
Game Manager — Unified controller for round-based gameplay.

Orchestrates all canonical modules:
  - TurretModel (turret/model.py)
  - BallisticsEngine (ballistics/engine.py)
  - TargetManager (targets/manager.py)
  - WeatherConditions (ballistics/atmosphere.py)

Round flow:
  MENU → ROUND_START (countdown) → PLAYING → TARGET_HIT/TARGET_ESCAPED → ROUND_END → ...
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from enum import Enum

from ballistics.engine import BallisticsEngine
from ballistics.atmosphere import WeatherConditions, generate_random_weather
from turret.model import TurretModel, TurretConfig, TurretState
from targets.manager import TargetManager, Target, TargetType


class GameState(str, Enum):
    MENU = "menu"
    ROUND_START = "round_start"
    PLAYING = "playing"
    TARGET_HIT = "target_hit"
    TARGET_ESCAPED = "target_escaped"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"
    TRAINING = "training"             # Free-fire at static target
    TRAINING_RESPAWN = "training_respawn"  # Waiting to respawn static target


@dataclass
class RoundStats:
    round_number: int = 0
    target_type: str = ""
    target_hit: bool = False
    rounds_fired: int = 0
    time_to_hit: float = 0.0
    accuracy: float = 0.0


@dataclass
class GameStats:
    total_rounds: int = 0
    targets_hit: int = 0
    targets_missed: int = 0
    total_ammo_used: int = 0
    total_time: float = 0.0
    round_stats: List[RoundStats] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        if self.total_rounds == 0:
            return 0.0
        return self.targets_hit / self.total_rounds * 100

    @property
    def accuracy(self) -> float:
        if self.total_ammo_used == 0:
            return 0.0
        return self.targets_hit / self.total_ammo_used * 100


# Round progression: Shahed-136 attack scenarios
ROUND_SEQUENCE = [
    (TargetType.SHAHED_136, "Shahed-136 — approach"),
    (TargetType.SHAHED_136, "Shahed-136 — at distance"),
    (TargetType.SHAHED_136, "Shahed-136 — high altitude"),
    (TargetType.SHAHED_136, "Shahed-136 — fast approach"),
    (TargetType.SHAHED_136, "Shahed-136 — crossing"),
    (TargetType.SHAHED_136, "Shahed-136 — long range"),
    (TargetType.SHAHED_136, "Shahed-136 — final"),
]


class GameManager:
    """
    Main game logic controller.
    Manages rounds, targets, turret, ballistics, and scoring.
    """

    def __init__(self):
        # Weather (randomized per round)
        self.weather = generate_random_weather()

        # Core modules
        self.turret = TurretModel()
        self.engine = BallisticsEngine(drag_model="G7")
        self.engine.set_weather(self.weather)
        self.target_manager = TargetManager()

        # Wire turret firing to ballistics engine
        self.turret.set_fire_callback(self._on_turret_fire)
        self.turret.set_event_callback(self._on_turret_event)

        # Current target shortcut
        self.current_target: Optional[Target] = None

        # State
        self.state = GameState.MENU
        self.game_time = 0.0
        self.round_start_time = 0.0
        self.round_timer = 0.0
        self.countdown = 3.0
        self.round_number = 0

        # Stats
        self.stats = GameStats()
        self._round_ammo_start = 0

        # Event system
        self._event_listeners: List[Callable] = []
        self._pending_events: List[dict] = []

        # Round timing
        self.round_time_limit = 60.0
        self.post_hit_delay = 3.0
        self.post_hit_timer = 0.0

        # Training mode
        self.training_mode = False
        self.training_respawn_timer = 0.0
        self.training_respawn_delay = 3.0
        self.training_distance = 200.0  # meters
        self.training_hits = 0
        self.training_shots = 0

    # ---- Event system ----

    def add_event_listener(self, callback: Callable):
        self._event_listeners.append(callback)

    def _emit_event(self, event: dict):
        self._pending_events.append(event)
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                pass

    # ---- Turret callbacks ----

    def _on_turret_fire(self, muzzle_pos, azimuth, elevation):
        """Called when turret fires a round — spawns a projectile."""
        self.engine.fire(
            azimuth_rad=azimuth,
            elevation_rad=elevation,
            muzzle_offset=muzzle_pos,
            dispersion_moa=2.0,
        )

    def _on_turret_event(self, event_type, data):
        """Called for turret state events (overheat, reload, etc)."""
        event = {"type": event_type, **data}
        if event_type == "round_fired":
            event["type"] = "shot_fired"
        self._emit_event(event)

    # ---- Game flow ----

    def start_game(self):
        """Start a new game."""
        self.weather = generate_random_weather()
        self.engine = BallisticsEngine(drag_model="G7")
        self.engine.set_weather(self.weather)
        self.turret = TurretModel()
        self.turret.set_fire_callback(self._on_turret_fire)
        self.turret.set_event_callback(self._on_turret_event)
        self.target_manager = TargetManager()
        self.stats = GameStats()
        self.game_time = 0.0
        self.round_number = 0
        self._emit_event({
            "type": "game_started",
            "weather": {
                "temperature_c": round(self.weather.temperature_c, 1),
                "pressure_hpa": round(self.weather.pressure_hpa, 1),
                "humidity_pct": round(self.weather.humidity_pct, 1),
                "wind_speed_mps": round(self.weather.wind_speed_mps, 1),
                "wind_direction_deg": round(self.weather.wind_direction_deg, 1),
            }
        })
        self._start_round()

    def _start_round(self):
        """Begin a new round."""
        self.round_number += 1
        self.state = GameState.ROUND_START
        self.countdown = 3.0
        self.round_timer = 0.0
        self.engine.clear_all()
        self._round_ammo_start = self.turret.total_rounds_fired

        # Generate new weather per round
        self.weather = generate_random_weather()
        self.engine.set_weather(self.weather)

        # Spawn target based on round sequence
        seq_idx = (self.round_number - 1) % len(ROUND_SEQUENCE)
        target_type, description = ROUND_SEQUENCE[seq_idx]
        self.current_target = self.target_manager.spawn_target(target_type)

        self._emit_event({
            "type": "round_start",
            "round": self.round_number,
            "description": description,
            "target_type": target_type.value,
        })

    def next_round(self):
        """Advance to next round (called by UI or API)."""
        self._start_round()

    # ---- Training mode ----

    def start_training(self):
        """Start training mode with a static target at 200m."""
        self.training_mode = True
        self.training_hits = 0
        self.training_shots = 0
        self.weather = generate_random_weather()
        self.engine = BallisticsEngine(drag_model="G7")
        self.engine.set_weather(self.weather)
        self.turret = TurretModel()
        self.turret.set_fire_callback(self._on_turret_fire)
        self.turret.set_event_callback(self._on_turret_event)
        self.target_manager = TargetManager()
        self.stats = GameStats()
        self.game_time = 0.0

        self._emit_event({
            "type": "training_started",
            "distance": self.training_distance,
        })

        self._spawn_training_target()
        self.state = GameState.TRAINING

    def _spawn_training_target(self):
        """Spawn a static target due north at training distance."""
        self.engine.clear_all()
        # Static target: due north (+Y), at altitude
        target_height = 200.0  # 200m altitude
        self.current_target = self.target_manager.spawn_target(
            target_type=TargetType.SHAHED_136,
            forced_params={
                'position': [0, self.training_distance, target_height],
                'velocity': [0, 0, 0],  # Static — zero velocity
                'speed': 0,
            },
        )
        self._emit_event({
            "type": "training_target_spawned",
            "position": [0, self.training_distance, target_height],
        })

    # ---- Main update ----

    def update(self, dt: float) -> List[dict]:
        """
        Main game update loop. Called every frame.
        Returns list of events.
        """
        events = []
        self._pending_events = events
        self.game_time += dt

        # Always update turret servo (slew / heat dissipation) so the
        # player can aim freely before and between rounds.
        self.turret.update(dt)

        if self.state == GameState.MENU:
            # Block firing in menu — servo still works above
            self.turret.stop_firing()
            return events

        # === TRAINING MODE ===
        if self.state == GameState.TRAINING:
            self.engine.step(dt)
            # Check hits on static target
            if self.current_target and self.current_target.alive:
                hits = self.engine.check_all_hits(
                    self.current_target.position,
                    self.current_target.profile.hit_radius,
                )
                if hits:
                    self.current_target.alive = False
                    self.training_hits += 1
                    self.training_respawn_timer = self.training_respawn_delay
                    self.state = GameState.TRAINING_RESPAWN
                    events.append({
                        "type": "training_hit",
                        "hits": self.training_hits,
                    })
            self.engine.cleanup_dead(max_dead=50)
            return events

        if self.state == GameState.TRAINING_RESPAWN:
            self.turret.stop_firing()
            self.engine.step(dt)
            self.training_respawn_timer -= dt
            if self.training_respawn_timer <= 0:
                self._spawn_training_target()
                self.state = GameState.TRAINING
                events.append({"type": "training_target_spawned"})
            self.engine.cleanup_dead(max_dead=50)
            return events

        if self.state == GameState.ROUND_START:
            self.turret.stop_firing()
            self.countdown -= dt
            if self.countdown <= 0:
                self.state = GameState.PLAYING
                self.round_start_time = self.game_time
                events.append({"type": "round_active"})
            return events

        if self.state in (GameState.TARGET_HIT, GameState.TARGET_ESCAPED):
            self.turret.stop_firing()
            self.post_hit_timer -= dt
            if self.post_hit_timer <= 0:
                self.state = GameState.ROUND_END
                events.append({"type": "round_end_ready"})
            return events

        if self.state != GameState.PLAYING:
            self.turret.stop_firing()
            return events

        # === PLAYING STATE ===
        self.round_timer += dt

        # (turret.update already called above for all states)

        # Advance projectiles
        self.engine.step(dt)

        # Update target position
        self.target_manager.update(dt)
        self.current_target = self.target_manager.active_target

        # Check hits
        if self.current_target and self.current_target.alive:
            hits = self.engine.check_all_hits(
                self.current_target.position,
                self.current_target.profile.hit_radius,
            )
            if hits:
                self.current_target.alive = False
                self._on_target_hit()
                events.append({
                    "type": "target_hit",
                    "round": self.round_number,
                    "time": round(self.round_timer, 2),
                    "rounds_fired": self.turret.total_rounds_fired - self._round_ammo_start,
                })

        elif self.current_target and not self.current_target.alive:
            # Target left engagement zone
            self._on_target_escaped()
            events.append({
                "type": "target_escaped",
                "round": self.round_number,
            })

        # Check round time limit
        if self.round_timer > self.round_time_limit:
            self._on_target_escaped()
            events.append({"type": "round_timeout"})

        # Cleanup old projectiles
        self.engine.cleanup_dead(max_dead=50)

        return events

    # ---- Hit/miss handling ----

    def _on_target_hit(self):
        rounds_used = self.turret.total_rounds_fired - self._round_ammo_start
        self.stats.targets_hit += 1
        self.stats.total_rounds += 1
        self.stats.total_ammo_used += rounds_used
        self.stats.round_stats.append(RoundStats(
            round_number=self.round_number,
            target_type=self.current_target.profile.name if self.current_target else "",
            target_hit=True,
            rounds_fired=rounds_used,
            time_to_hit=self.round_timer,
            accuracy=(1 / rounds_used * 100) if rounds_used > 0 else 0,
        ))
        self.state = GameState.TARGET_HIT
        self.post_hit_timer = self.post_hit_delay
        self.turret.stop_firing()

    def _on_target_escaped(self):
        if self.state in (GameState.TARGET_HIT, GameState.TARGET_ESCAPED, GameState.ROUND_END):
            return  # Already handled
        rounds_used = self.turret.total_rounds_fired - self._round_ammo_start
        self.stats.targets_missed += 1
        self.stats.total_rounds += 1
        self.stats.total_ammo_used += rounds_used
        self.stats.round_stats.append(RoundStats(
            round_number=self.round_number,
            target_type=self.current_target.profile.name if self.current_target else "",
            target_hit=False,
            rounds_fired=rounds_used,
            time_to_hit=self.round_timer,
        ))
        self.state = GameState.TARGET_ESCAPED
        self.post_hit_timer = self.post_hit_delay
        self.turret.stop_firing()

    # ---- API helpers ----

    def get_monocular_view(self) -> dict:
        """Get monocular/scope view (target info only if in scope FOV)."""
        return self.target_manager.get_monocular_view(
            self.turret.azimuth,
            self.turret.elevation,
            fov_deg=10.0,
        )

    def get_full_status(self) -> dict:
        """Complete game status for API."""
        target_info = None
        if self.current_target and self.current_target.alive:
            target_info = self.target_manager.get_target_info()

        return {
            "game_state": self.state.value,
            "game_time": round(self.game_time, 2),
            "round": self.round_number,
            "round_timer": round(self.round_timer, 2),
            "countdown": round(max(0, self.countdown), 1),
            "turret": self.turret.get_status(),
            "target": target_info,
            "monocular": self.get_monocular_view(),
            "weather": {
                "temperature_c": round(self.weather.temperature_c, 1),
                "pressure_hpa": round(self.weather.pressure_hpa, 1),
                "humidity_pct": round(self.weather.humidity_pct, 1),
                "wind_speed_mps": round(self.weather.wind_speed_mps, 1),
                "wind_direction_deg": round(self.weather.wind_direction_deg, 1),
            },
            "stats": {
                "targets_hit": self.stats.targets_hit,
                "targets_missed": self.stats.targets_missed,
                "hit_rate": round(self.stats.hit_rate, 1),
                "total_ammo_used": self.stats.total_ammo_used,
            },
            "active_bullets": len([s for s, t in self.engine.projectiles if s.alive]),
        }
